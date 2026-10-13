import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropUpdate } from '../api/cropJourney.ts'
import type { GrowOffer } from '../api/growOffers.ts'
import {
  buildCropCommitment,
  buildCropUpdate,
  buildFarm,
  buildGrowOffer,
  buildUser,
  installFakeApi,
} from '../test/fakeApi.ts'
import { renderApp } from '../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })
const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })

const journey: CropUpdate[] = [
  buildCropUpdate({ id: 1, stage: 'PLANNED', message: 'Seed ordered and beds prepared.' }),
  buildCropUpdate({
    id: 2,
    stage: 'PLANTED',
    message: 'Seedlings went into the ground today.',
    image_url: 'https://photos.example.com/okra-seedlings.jpg',
    created_at: '2026-04-15T14:00:00Z',
  }),
]

function openAsCustomer(offer: Partial<GrowOffer>, cropUpdates: CropUpdate[] = journey) {
  const api = installFakeApi({
    accounts: [{ user: customer, password: 'correct-horse-battery' }],
    commitments: [buildCropCommitment({ offer: { id: 1, ...offer } })],
    cropUpdates,
  })
  api.signIn(customer)
  renderApp('/customer/grow-offers/1')
  return api
}

function openAsFarmer(offer: Partial<GrowOffer>, cropUpdates: CropUpdate[] = journey) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms: [farm],
    growOffers: [buildGrowOffer({ id: 1, ...offer })],
    cropUpdates,
  })
  api.signIn(farmer)
  renderApp('/farmer/grow-on-demand/1')
  return api
}

async function findSection(name: string) {
  return within(await screen.findByRole('region', { name }))
}

function stageNames(section: Awaited<ReturnType<typeof findSection>>) {
  return section.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)
}

describe('customer view of a crop journey', () => {
  it('shows the offer and its updates in the order they happened', async () => {
    openAsCustomer({ status: 'GROWING' })

    const offer = await findSection('Okra')
    expect(offer.getByText('Growing')).toBeInTheDocument()
    expect(
      offer.getByText('Green Acres, Charlotte, NC · About $3.50 / lb · Expected harvest Jul 1, 2026'),
    ).toBeInTheDocument()
    expect(offer.getByText('12 / 20 customers committed')).toBeInTheDocument()

    const updates = await findSection('Crop journey')
    expect(stageNames(updates)).toEqual(['Planned', 'Planted'])
    expect(updates.getByText('Seed ordered and beds prepared.')).toBeInTheDocument()
    expect(updates.getByText('Seedlings went into the ground today.')).toBeInTheDocument()
  })

  it('offers the photo as a link that opens separately, never as an embedded image', async () => {
    openAsCustomer({ status: 'GROWING' })
    const updates = await findSection('Crop journey')

    const photoLink = updates.getByRole('link', { name: 'View photo' })

    expect(photoLink).toHaveAttribute('href', 'https://photos.example.com/okra-seedlings.jpg')
    expect(photoLink).toHaveAttribute('target', '_blank')
    expect(photoLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(updates.queryByRole('img')).not.toBeInTheDocument()
  })

  it('gives a customer nothing to post with', async () => {
    openAsCustomer({ status: 'GROWING' })
    await findSection('Crop journey')

    expect(screen.queryByRole('region', { name: 'Post Crop Update' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark completed' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to grow offers' })).toHaveAttribute(
      'href',
      '/customer/grow-offers',
    )
  })

  it('says so when the farmer has not posted anything yet', async () => {
    openAsCustomer({ status: 'CONFIRMED' }, [])

    const updates = await findSection('Crop journey')

    expect(updates.getByText(/No updates yet/)).toBeInTheDocument()
  })

  it('is reached from the list of commitments', async () => {
    const api = installFakeApi({
      accounts: [{ user: customer, password: 'correct-horse-battery' }],
      commitments: [buildCropCommitment({ offer: { id: 1, status: 'GROWING' } })],
      cropUpdates: journey,
    })
    api.signIn(customer)
    renderApp('/customer/grow-offers')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('link', { name: 'View crop journey for Okra' }))

    const updates = await findSection('Crop journey')
    expect(stageNames(updates)).toEqual(['Planned', 'Planted'])
  })

  it('shows an error when the offer does not exist', async () => {
    const api = installFakeApi({ accounts: [{ user: customer, password: 'correct-horse-battery' }] })
    api.signIn(customer)
    renderApp('/customer/grow-offers/999')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The crop journey could not be loaded. Grow offer not found',
    )
  })
})

describe('farmer posting crop updates', () => {
  it('posts an update, adds it to the journey and shows the new offer status', async () => {
    const api = openAsFarmer({ status: 'CONFIRMED' }, [journey[0]])
    const user = userEvent.setup()
    const form = await findSection('Post Crop Update')

    await user.selectOptions(form.getByLabelText('Stage'), 'Planted')
    await user.type(form.getByLabelText('Message'), 'Seedlings went into the ground today.')
    await user.type(form.getByLabelText('Photo link'), 'https://photos.example.com/okra.jpg')
    await user.click(form.getByRole('button', { name: 'Post Crop Update' }))

    expect(
      await screen.findByText(
        'Your update has been posted and committed customers have been notified.',
      ),
    ).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/grow-offers/1/updates')[0].body).toEqual({
      stage: 'PLANTED',
      message: 'Seedlings went into the ground today.',
      image_url: 'https://photos.example.com/okra.jpg',
    })
    const updates = await findSection('Crop journey')
    expect(stageNames(updates)).toEqual(['Planned', 'Planted'])
    // Planting a confirmed offer starts it growing.
    expect((await findSection('Okra')).getByText('Growing')).toBeInTheDocument()
  })

  it('offers only stages from the latest one onward', async () => {
    openAsFarmer({ status: 'GROWING' }, [
      journey[0],
      buildCropUpdate({ id: 2, stage: 'FLOWERING' }),
    ])
    const form = await findSection('Post Crop Update')

    const stages = within(form.getByLabelText('Stage'))
      .getAllByRole('option')
      .map((option) => option.textContent)

    expect(stages).toEqual(['Flowering', 'Harvest soon', 'Ready'])
  })

  it('offers only the planned stage while the offer is still open', async () => {
    openAsFarmer({ status: 'OPEN' }, [])
    const form = await findSection('Post Crop Update')

    const stages = within(form.getByLabelText('Stage'))
      .getAllByRole('option')
      .map((option) => option.textContent)

    expect(stages).toEqual(['Planned'])
    expect(
      form.getByText('This offer is not confirmed yet, so only a Planned update can be posted.'),
    ).toBeInTheDocument()
  })

  it.each([
    ['   ', 'https://photos.example.com/okra.jpg', 'Write a short message about how the crop is doing.'],
    ['Looking good.', 'http://photos.example.com/okra.jpg', 'The photo link must start with https://'],
  ])('rejects message "%s" with photo "%s" without calling the API', async (message, photo, error) => {
    const api = openAsFarmer({ status: 'CONFIRMED' }, [])
    const user = userEvent.setup()
    const form = await findSection('Post Crop Update')

    await user.type(form.getByLabelText('Message'), message)
    await user.type(form.getByLabelText('Photo link'), photo)
    await user.click(form.getByRole('button', { name: 'Post Crop Update' }))

    expect(await form.findByRole('alert')).toHaveTextContent(error)
    expect(api.requestsTo('POST', '/api/grow-offers/1/updates')).toHaveLength(0)
  })

  it('shows the server message when the update is refused', async () => {
    const api = openAsFarmer({ status: 'CONFIRMED' }, [])
    api.failNextRequest(
      'POST',
      '/api/grow-offers/1/updates',
      403,
      'You can only manage your own grow offers',
    )
    const user = userEvent.setup()
    const form = await findSection('Post Crop Update')

    await user.type(form.getByLabelText('Message'), 'Looking good.')
    await user.click(form.getByRole('button', { name: 'Post Crop Update' }))

    expect(await form.findByRole('alert')).toHaveTextContent(
      'You can only manage your own grow offers',
    )
  })

  it('marks a ready offer completed and then stops accepting updates', async () => {
    const api = openAsFarmer({ status: 'READY' }, [buildCropUpdate({ id: 1, stage: 'READY' })])
    const user = userEvent.setup()
    const form = await findSection('Post Crop Update')

    await user.click(form.getByRole('button', { name: 'Mark completed' }))

    expect(
      await screen.findByText('This grow offer has been marked completed.'),
    ).toBeInTheDocument()
    expect((await findSection('Okra')).getByText('Completed')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Post Crop Update' })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/grow-offers/1/complete')).toHaveLength(1)
  })

  it.each(['COMPLETED', 'CANCELLED'] as const)(
    'shows no posting controls for a %s offer',
    async (status) => {
      openAsFarmer({ status })
      await findSection('Crop journey')

      expect(screen.queryByRole('region', { name: 'Post Crop Update' })).not.toBeInTheDocument()
    },
  )

  it('offers to mark completed only when the crop is ready', async () => {
    openAsFarmer({ status: 'GROWING' })
    await findSection('Post Crop Update')

    expect(screen.queryByRole('button', { name: 'Mark completed' })).not.toBeInTheDocument()
  })

  it('is reached from the list of grow offers', async () => {
    const api = installFakeApi({
      accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
      farms: [farm],
      growOffers: [buildGrowOffer({ id: 1, status: 'CONFIRMED' })],
      cropUpdates: journey,
    })
    api.signIn(farmer)
    renderApp('/farmer/grow-on-demand')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('link', { name: 'Crop journey for Okra' }))

    expect(await screen.findByRole('region', { name: 'Post Crop Update' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to Grow-On-Demand' })).toBeInTheDocument()
  })
})
