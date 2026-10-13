import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropPoll } from '../../api/cropPolls.ts'
import { buildCropPoll, buildFarm, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })

function openCropPolls(cropPolls: CropPoll[] = []) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms: [farm],
    cropPolls,
  })
  api.signIn(farmer)
  renderApp('/farmer/crop-polls')
  return api
}

describe('farmer crop polls', () => {
  it('explains what polls are for when there are none', async () => {
    openCropPolls()

    expect(await screen.findByText(/You have not created any polls yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Crop Poll' })).toBeInTheDocument()
  })

  it('shows each poll with its vote counts and status', async () => {
    openCropPolls([
      buildCropPoll({ id: 1 }),
      buildCropPoll({ id: 2, question: 'Which greens for fall?', status: 'CLOSED', options: [] }),
    ])

    const openPoll = within(
      (await screen.findByRole('heading', { name: 'What should I grow next?' })).closest('li')!,
    )
    expect(openPoll.getByText('Open')).toBeInTheDocument()
    expect(openPoll.getByText('10 votes in total')).toBeInTheDocument()
    expect(openPoll.getByText('6 votes')).toBeInTheDocument()
    expect(openPoll.getByText('3 votes')).toBeInTheDocument()
    expect(openPoll.getByText('1 vote')).toBeInTheDocument()
    expect(openPoll.getByRole('button', { name: /Close poll/ })).toBeInTheDocument()

    const closedPoll = within(
      screen.getByRole('heading', { name: 'Which greens for fall?' }).closest('li')!,
    )
    expect(closedPoll.getByText('Closed')).toBeInTheDocument()
    expect(closedPoll.queryByRole('button', { name: /Close poll/ })).not.toBeInTheDocument()
  })

  it('creates a poll with the default question and the crops entered', async () => {
    const api = openCropPolls()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Crop Poll' }))
    expect(screen.getByLabelText('Question')).toHaveValue('What should I grow next?')
    await user.type(screen.getByLabelText('Crop 1'), 'okra')
    await user.type(screen.getByLabelText('Crop 2'), 'sweet corn')
    await user.click(screen.getByRole('button', { name: 'Create poll' }))

    expect(
      await screen.findByText('Your poll is open. Nearby customers can now vote.'),
    ).toBeInTheDocument()
    // The third box was left empty and is not sent.
    expect(api.requestsTo('POST', '/api/crop-polls')[0].body).toEqual({
      question: 'What should I grow next?',
      options: ['okra', 'sweet corn'],
    })
    const poll = within(
      screen.getByRole('heading', { name: 'What should I grow next?' }).closest('li')!,
    )
    expect(poll.getByText('Okra')).toBeInTheDocument()
    expect(poll.getByText('Sweet Corn')).toBeInTheDocument()
    expect(poll.getByText('0 votes in total')).toBeInTheDocument()
  })

  it('lets the farmer add more crops, up to eight', async () => {
    openCropPolls()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Crop Poll' }))
    for (let count = 3; count < 8; count += 1) {
      await user.click(screen.getByRole('button', { name: 'Add another crop' }))
    }

    expect(screen.getByLabelText('Crop 8')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add another crop' })).not.toBeInTheDocument()
  })

  it.each([
    [['okra'], 'Give customers at least 2 crops to choose between.'],
    [['okra', ' OKRA '], 'Each crop can appear only once.'],
  ])('rejects the crops %j without calling the API', async (crops, message) => {
    const api = openCropPolls()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Crop Poll' }))
    for (const [index, crop] of crops.entries()) {
      await user.type(screen.getByLabelText(`Crop ${index + 1}`), crop)
    }
    await user.click(screen.getByRole('button', { name: 'Create poll' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(api.requestsTo('POST', '/api/crop-polls')).toHaveLength(0)
  })

  it('closes an open poll', async () => {
    const api = openCropPolls([buildCropPoll({ id: 4 })])
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole('button', { name: 'Close poll: What should I grow next?' }),
    )

    expect(await screen.findByText('Closed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Close poll/ })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/crop-polls/4/close')).toHaveLength(1)
  })

  it('shows the server message when closing is refused', async () => {
    const api = openCropPolls([buildCropPoll({ id: 4 })])
    api.failNextRequest('POST', '/api/crop-polls/4/close', 409, 'This crop poll is already closed')
    const user = userEvent.setup()

    await user.click(
      await screen.findByRole('button', { name: 'Close poll: What should I grow next?' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('This crop poll is already closed')
  })
})
