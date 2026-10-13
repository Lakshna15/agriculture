import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropPollSearchResult, CropVote } from '../../api/cropPolls.ts'
import { buildCropPollSearchResult, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })

function openCropPolls(data: {
  cropPollSearchResults?: CropPollSearchResult[]
  cropVotes?: CropVote[]
}) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    ...data,
  })
  api.signIn(customer)
  renderApp('/customer/crop-polls')
  return api
}

async function search(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Latitude'), '35.227')
  await user.type(screen.getByLabelText('Longitude'), '-80.843')
  await user.click(screen.getByRole('button', { name: 'Search' }))
}

async function findPollCard(question: string) {
  const results = within(await screen.findByRole('region', { name: 'Crop polls found' }))
  return within((await results.findByRole('heading', { name: question })).closest('li')!)
}

describe('customer crop polls', () => {
  it('shows a nearby poll with its farm and the crops to choose between', async () => {
    openCropPolls({ cropPollSearchResults: [buildCropPollSearchResult()] })
    const user = userEvent.setup()
    await search(user)

    const card = await findPollCard('What should I grow next?')

    expect(card.getByText('Green Acres · Charlotte, NC · 3.2 mi')).toBeInTheDocument()
    expect(card.getAllByRole('radio').map((radio) => radio.closest('label')?.textContent)).toEqual([
      'Okra',
      'Sweet Corn',
      'Collard Greens',
    ])
    expect(card.getByRole('button', { name: 'Vote' })).toBeInTheDocument()
  })

  it('casts a vote and then shows the results with the choice marked', async () => {
    const api = openCropPolls({ cropPollSearchResults: [buildCropPollSearchResult()] })
    const user = userEvent.setup()
    await search(user)
    const card = await findPollCard('What should I grow next?')

    await user.click(card.getByRole('radio', { name: 'Sweet Corn' }))
    await user.click(card.getByRole('button', { name: 'Vote' }))

    expect(await card.findByText('Your vote')).toBeInTheDocument()
    expect(card.getByText('Your vote').closest('li')).toHaveTextContent('Sweet Corn')
    expect(card.getByText('4 votes')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: 'Vote' })).not.toBeInTheDocument()
    expect(card.queryByRole('radio')).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/crop-votes')).toEqual([
      { method: 'POST', path: '/api/crop-votes', body: { poll_id: 1, option_id: 2 } },
    ])
  })

  it('asks for a choice before voting', async () => {
    const api = openCropPolls({ cropPollSearchResults: [buildCropPollSearchResult()] })
    const user = userEvent.setup()
    await search(user)
    const card = await findPollCard('What should I grow next?')

    await user.click(card.getByRole('button', { name: 'Vote' }))

    expect(await card.findByRole('alert')).toHaveTextContent('Choose a crop to vote for.')
    expect(api.requestsTo('POST', '/api/crop-votes')).toHaveLength(0)
  })

  it('shows results instead of the ballot for a poll already voted in', async () => {
    openCropPolls({
      cropPollSearchResults: [buildCropPollSearchResult()],
      cropVotes: [{ poll_id: 1, option_id: 1 }],
    })
    const user = userEvent.setup()
    await search(user)

    const card = await findPollCard('What should I grow next?')

    expect(await card.findByText('Your vote')).toBeInTheDocument()
    expect(card.getByText('Your vote').closest('li')).toHaveTextContent('Okra')
    expect(card.getByText('6 votes')).toBeInTheDocument()
    expect(card.getByText('1 vote')).toBeInTheDocument()
    expect(card.queryByRole('button', { name: 'Vote' })).not.toBeInTheDocument()
    expect(
      card.getByRole('progressbar', { name: 'Share of votes for Okra' }),
    ).toHaveAttribute('aria-valuenow', '60')
  })

  it('shows the server message when the vote is refused', async () => {
    const api = openCropPolls({ cropPollSearchResults: [buildCropPollSearchResult()] })
    api.failNextRequest('POST', '/api/crop-votes', 409, 'This crop poll is closed')
    const user = userEvent.setup()
    await search(user)
    const card = await findPollCard('What should I grow next?')

    await user.click(card.getByRole('radio', { name: 'Okra' }))
    await user.click(card.getByRole('button', { name: 'Vote' }))

    expect(await card.findByRole('alert')).toHaveTextContent('This crop poll is closed')
    expect(card.getByRole('button', { name: 'Vote' })).toBeEnabled()
  })

  it('points to crop requests when there are no polls nearby', async () => {
    openCropPolls({})
    const user = userEvent.setup()
    await search(user)

    expect(await screen.findByText('No open crop polls within 25 miles.')).toBeInTheDocument()
    expect(screen.getByText(/request a crop under Crop requests/)).toBeInTheDocument()
  })
})
