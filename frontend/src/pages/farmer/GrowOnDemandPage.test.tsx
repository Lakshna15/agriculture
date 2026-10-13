import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropDemand } from '../../api/cropRequests.ts'
import type { GrowOffer } from '../../api/growOffers.ts'
import {
  buildCropDemand,
  buildFarm,
  buildGrowOffer,
  buildUser,
  installFakeApi,
} from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farm = buildFarm({ id: 3, owner_id: farmer.id })

function openGrowOnDemand(data: { demand?: CropDemand[]; growOffers?: GrowOffer[] } = {}) {
  const api = installFakeApi({
    accounts: [{ user: farmer, password: 'tractor-barn-orchard' }],
    farms: [farm],
    ...data,
  })
  api.signIn(farmer)
  renderApp('/farmer/grow-on-demand')
  return api
}

async function findSection(name: string) {
  return within(await screen.findByRole('region', { name }))
}

async function fillOfferForm(
  section: Awaited<ReturnType<typeof findSection>>,
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.type(section.getByLabelText('Expected quantity'), '100')
  await user.type(section.getByLabelText('Estimated price'), '3.50')
  await user.type(section.getByLabelText('Planting date'), '2030-04-15')
  await user.type(section.getByLabelText('Expected harvest date'), '2030-07-01')
  await user.type(section.getByLabelText('Minimum customers'), '20')
}

describe('local demand', () => {
  it('shows how many customers want each crop and how much', async () => {
    openGrowOnDemand({
      demand: [
        buildCropDemand(),
        buildCropDemand({
          crop_name: 'Sweet Corn',
          unit: 'EACH',
          customers_interested: 1,
          estimated_weekly_quantity: 9.5,
          one_time_quantity: 24,
        }),
        buildCropDemand({
          crop_name: 'Bok Choy',
          unit: 'BUNCH',
          customers_interested: 3,
          estimated_weekly_quantity: 0,
          one_time_quantity: 12,
        }),
      ],
    })
    const demand = await findSection('Local demand')

    const okra = within((await demand.findByRole('heading', { name: 'Okra' })).closest('li')!)
    expect(okra.getByText('42 customers interested')).toBeInTheDocument()
    expect(okra.getByText('126 lb/week estimated demand')).toBeInTheDocument()
    expect(okra.queryByText(/one-time requests/)).not.toBeInTheDocument()

    const corn = within(demand.getByRole('heading', { name: 'Sweet Corn' }).closest('li')!)
    expect(corn.getByText('1 customer interested')).toBeInTheDocument()
    expect(corn.getByText('9.5 each/week estimated demand')).toBeInTheDocument()
    expect(corn.getByText('24 each in one-time requests')).toBeInTheDocument()

    const bokChoy = within(demand.getByRole('heading', { name: 'Bok Choy' }).closest('li')!)
    expect(bokChoy.queryByText(/week estimated demand/)).not.toBeInTheDocument()
    expect(bokChoy.getByText('12 bunch in one-time requests')).toBeInTheDocument()
  })

  it('says so when there is no unmet demand nearby', async () => {
    openGrowOnDemand()

    const demand = await findSection('Local demand')

    expect(
      await demand.findByText(/No unmet crop requests near your farm right now/),
    ).toBeInTheDocument()
  })

  it('tells a farmer without a farm to create one first', async () => {
    const api = openGrowOnDemand()
    api.failNextRequest('GET', '/api/demand', 409, 'Create your farm first')

    const demand = await findSection('Local demand')

    expect(await demand.findByRole('alert')).toHaveTextContent(
      'Local demand could not be loaded. Create your farm first',
    )
  })
})

describe('creating a grow offer', () => {
  it('starts from a demand row with the crop and unit filled in', async () => {
    const api = openGrowOnDemand({ demand: [buildCropDemand()] })
    const user = userEvent.setup()
    const demand = await findSection('Local demand')
    const offers = await findSection('Your grow offers')

    await user.click(await demand.findByRole('button', { name: 'Create grow offer for Okra' }))
    expect(offers.getByLabelText('Crop')).toHaveValue('Okra')
    expect(offers.getByLabelText('Unit')).toHaveValue('LB')

    await fillOfferForm(offers, user)
    await user.click(offers.getByRole('button', { name: 'Create offer' }))

    expect(
      await offers.findByText('Your grow offer for Okra is open for commitments.'),
    ).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/grow-offers')[0].body).toEqual({
      crop_name: 'Okra',
      expected_quantity: 100,
      unit: 'LB',
      estimated_price: '3.50',
      planting_date: '2030-04-15',
      expected_harvest_date: '2030-07-01',
      minimum_customers: 20,
    })

    const card = within(offers.getByRole('heading', { name: 'Okra' }).closest('li')!)
    expect(card.getByText('Open')).toBeInTheDocument()
    expect(card.getByText('0 / 20 customers committed')).toBeInTheDocument()
  })

  it('can be started without picking a demand row', async () => {
    openGrowOnDemand()
    const user = userEvent.setup()
    const offers = await findSection('Your grow offers')

    await user.click(await offers.findByRole('button', { name: 'Create Grow Offer' }))

    expect(offers.getByLabelText('Crop')).toHaveValue('')
    expect(offers.getByLabelText('Unit')).toHaveValue('')
  })

  it.each([
    ['Expected harvest date', '2030-03-01', 'The expected harvest date must not be before the planting date.'],
    ['Minimum customers', '0', 'Minimum customers must be a whole number of at least 1.'],
    ['Estimated price', '0', 'Estimated price must be more than zero'],
    ['Expected quantity', '2.5', 'Expected quantity must be a whole number of at least 1.'],
  ])('rejects an invalid %s without calling the API', async (fieldLabel, value, message) => {
    const api = openGrowOnDemand({ demand: [buildCropDemand()] })
    const user = userEvent.setup()
    const demand = await findSection('Local demand')
    const offers = await findSection('Your grow offers')

    await user.click(await demand.findByRole('button', { name: 'Create grow offer for Okra' }))
    await fillOfferForm(offers, user)
    await user.clear(offers.getByLabelText(fieldLabel))
    await user.type(offers.getByLabelText(fieldLabel), value)
    await user.click(offers.getByRole('button', { name: 'Create offer' }))

    expect(await offers.findByRole('alert')).toHaveTextContent(message)
    expect(api.requestsTo('POST', '/api/grow-offers')).toHaveLength(0)
  })
})

describe('your grow offers', () => {
  it('says so when the farmer has made no offers', async () => {
    openGrowOnDemand()

    const offers = await findSection('Your grow offers')

    expect(
      await offers.findByText(/You have not created any grow offers yet/),
    ).toBeInTheDocument()
  })

  it('shows each offer with its status and commitment progress', async () => {
    openGrowOnDemand({
      growOffers: [
        buildGrowOffer({ id: 1 }),
        buildGrowOffer({
          id: 2,
          crop_name: 'Sweet Corn',
          unit: 'EACH',
          status: 'CONFIRMED',
          minimum_customers: 5,
          committed_customers: 7,
          committed_quantity: 84,
          expected_quantity: 200,
        }),
      ],
    })
    const offers = await findSection('Your grow offers')

    const okra = within((await offers.findByRole('heading', { name: 'Okra' })).closest('li')!)
    expect(okra.getByText('Open')).toBeInTheDocument()
    expect(okra.getByText('12 / 20 customers committed')).toBeInTheDocument()
    expect(okra.getByText('40 of 100 lb spoken for')).toBeInTheDocument()
    expect(
      okra.getByText(
        '100 lb at about $3.50 / lb · Planting Apr 15, 2026 · Harvest Jul 1, 2026',
      ),
    ).toBeInTheDocument()

    const corn = within(offers.getByRole('heading', { name: 'Sweet Corn' }).closest('li')!)
    expect(corn.getByText('Confirmed')).toBeInTheDocument()
    expect(corn.getByText('7 / 5 customers committed')).toBeInTheDocument()
  })

  it('cancels an open offer', async () => {
    const api = openGrowOnDemand({ growOffers: [buildGrowOffer({ id: 6 })] })
    const user = userEvent.setup()
    const offers = await findSection('Your grow offers')

    await user.click(await offers.findByRole('button', { name: 'Cancel grow offer for Okra' }))

    expect(await offers.findByText('Cancelled')).toBeInTheDocument()
    expect(offers.queryByRole('button', { name: /Cancel grow offer/ })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/grow-offers/6/cancel')).toHaveLength(1)
  })

  it.each(['GROWING', 'READY', 'COMPLETED', 'CANCELLED'] as const)(
    'offers no cancel button for a %s offer',
    async (status) => {
      openGrowOnDemand({ growOffers: [buildGrowOffer({ status })] })
      const offers = await findSection('Your grow offers')

      await offers.findByRole('heading', { name: 'Okra' })

      expect(offers.queryByRole('button', { name: /Cancel grow offer/ })).not.toBeInTheDocument()
    },
  )

  it('shows the server message when cancelling is refused', async () => {
    const api = openGrowOnDemand({ growOffers: [buildGrowOffer({ id: 6 })] })
    api.failNextRequest(
      'POST',
      '/api/grow-offers/6/cancel',
      409,
      'Only an open or confirmed grow offer can be cancelled',
    )
    const user = userEvent.setup()
    const offers = await findSection('Your grow offers')

    await user.click(await offers.findByRole('button', { name: 'Cancel grow offer for Okra' }))

    expect(await offers.findByRole('alert')).toHaveTextContent(
      'Only an open or confirmed grow offer can be cancelled',
    )
    expect(offers.getByText('Open')).toBeInTheDocument()
  })
})
