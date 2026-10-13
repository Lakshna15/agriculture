import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CropRequest } from '../../api/cropRequests.ts'
import { buildCropRequest, buildUser, installFakeApi } from '../../test/fakeApi.ts'
import { renderApp } from '../../test/renderApp.tsx'

const customer = buildUser({ id: 1, name: 'Ana Grower', email: 'ana@example.com', role: 'CUSTOMER' })
const customerAccount = { user: customer, password: 'correct-horse-battery' }

function openCropRequests(cropRequests: CropRequest[] = []) {
  const api = installFakeApi({ accounts: [customerAccount], cropRequests })
  api.signIn(customer)
  renderApp('/customer/crop-requests')
  return api
}

async function findSection(name: string) {
  return within(await screen.findByRole('region', { name }))
}

async function fillRequestForm(user: ReturnType<typeof userEvent.setup>) {
  const form = await findSection('Request a crop')
  await user.type(form.getByLabelText('Crop'), 'okra')
  await user.type(form.getByLabelText('Quantity'), '3')
  await user.selectOptions(form.getByLabelText('Unit'), 'lb')
  await user.type(form.getByLabelText('Latitude'), '35.227')
  await user.type(form.getByLabelText('Longitude'), '-80.843')
  return form
}

describe('requesting a crop', () => {
  it('sends the request and adds it to the list', async () => {
    const api = openCropRequests()
    const user = userEvent.setup()

    const form = await fillRequestForm(user)
    await user.selectOptions(form.getByLabelText('How often'), 'Every month')
    await user.selectOptions(form.getByLabelText('How far you would travel'), '50 miles')
    await user.selectOptions(form.getByLabelText('Preferred season'), 'Summer')
    await user.type(form.getByLabelText('Notes'), 'For gumbo.')
    await user.click(form.getByRole('button', { name: 'Request this crop' }))

    expect(await form.findByRole('status')).toHaveTextContent(
      'Your request for Okra has been sent.',
    )
    expect(api.requestsTo('POST', '/api/crop-requests')[0].body).toEqual({
      crop_name: 'okra',
      quantity: 3,
      unit: 'LB',
      frequency: 'MONTHLY',
      latitude: 35.227,
      longitude: -80.843,
      radius_miles: 50,
      preferred_season: 'SUMMER',
      notes: 'For gumbo.',
    })

    const requests = await findSection('My crop requests')
    expect(requests.getByRole('heading', { name: 'Okra' })).toBeInTheDocument()
    expect(requests.getByText('3 lb every month')).toBeInTheDocument()
    expect(requests.getByText('From farms within 50 miles')).toBeInTheDocument()
    expect(requests.getByText('Open')).toBeInTheDocument()
  })

  it('sends the defaults when only the required fields are filled', async () => {
    const api = openCropRequests()
    const user = userEvent.setup()

    const form = await fillRequestForm(user)
    await user.click(form.getByRole('button', { name: 'Request this crop' }))

    await form.findByRole('status')
    expect(api.requestsTo('POST', '/api/crop-requests')[0].body).toMatchObject({
      frequency: 'WEEKLY',
      radius_miles: 25,
      preferred_season: null,
      notes: null,
    })
  })

  it.each([
    ['Quantity', '0', 'Quantity must be a whole number of at least 1.'],
    ['Quantity', '2.5', 'Quantity must be a whole number of at least 1.'],
    ['Latitude', '95', 'Latitude must be a number between -90 and 90.'],
  ])('rejects %s "%s" without calling the API', async (fieldLabel, value, message) => {
    const api = openCropRequests()
    const user = userEvent.setup()

    const form = await fillRequestForm(user)
    await user.clear(form.getByLabelText(fieldLabel))
    await user.type(form.getByLabelText(fieldLabel), value)
    await user.click(form.getByRole('button', { name: 'Request this crop' }))

    expect(await form.findByRole('alert')).toHaveTextContent(message)
    expect(api.requestsTo('POST', '/api/crop-requests')).toHaveLength(0)
  })

  it('shows the server message when the crop has already been requested', async () => {
    openCropRequests([buildCropRequest({ crop_name: 'Okra' })])
    const user = userEvent.setup()

    const form = await fillRequestForm(user)
    await user.click(form.getByRole('button', { name: 'Request this crop' }))

    expect(await form.findByRole('alert')).toHaveTextContent(
      'You already have an open request for Okra',
    )
  })
})

describe('arriving from an empty search', () => {
  it('offers to request the crop and carries the search term and location over', async () => {
    const api = installFakeApi({ accounts: [customerAccount] })
    api.signIn(customer)
    renderApp('/customer')
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Search term'), 'okra')
    await user.type(screen.getByLabelText('Latitude'), '35.227')
    await user.type(screen.getByLabelText('Longitude'), '-80.843')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText("Can't find this crop nearby?")).toBeInTheDocument()
    expect(screen.getByText('Request it from local farmers.')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Request this crop' }))

    const form = await findSection('Request a crop')
    expect(form.getByLabelText('Crop')).toHaveValue('okra')
    expect(form.getByLabelText('Latitude')).toHaveValue('35.227')
    expect(form.getByLabelText('Longitude')).toHaveValue('-80.843')
  })
})

describe('my crop requests', () => {
  it('explains what crop requests are for when there are none', async () => {
    openCropRequests()

    const requests = await findSection('My crop requests')

    expect(
      await requests.findByText(/You have not requested any crops yet/),
    ).toBeInTheDocument()
  })

  it('shows each request with its details and status', async () => {
    openCropRequests([
      buildCropRequest({ id: 1, crop_name: 'Okra', notes: 'For gumbo.' }),
      buildCropRequest({
        id: 2,
        crop_name: 'Sweet Corn',
        quantity: 12,
        unit: 'EACH',
        frequency: 'ONE_TIME',
        radius_miles: 10,
        preferred_season: null,
        covered_by_commitment: true,
      }),
      buildCropRequest({ id: 3, crop_name: 'Bok Choy', status: 'CANCELLED' }),
    ])
    const requests = await findSection('My crop requests')

    const okra = within((await requests.findByRole('heading', { name: 'Okra' })).closest('li')!)
    expect(okra.getByText('3 lb every week')).toBeInTheDocument()
    expect(okra.getByText('From farms within 25 miles')).toBeInTheDocument()
    expect(okra.getByText('Preferred season: Summer')).toBeInTheDocument()
    expect(okra.getByText('For gumbo.')).toBeInTheDocument()
    expect(okra.getByText('Open')).toBeInTheDocument()
    expect(okra.getByRole('button', { name: 'Cancel request for Okra' })).toBeInTheDocument()

    const corn = within(requests.getByRole('heading', { name: 'Sweet Corn' }).closest('li')!)
    expect(corn.getByText('12 each one time')).toBeInTheDocument()
    expect(corn.getByText('Covered by a grow offer you joined')).toBeInTheDocument()
    expect(corn.queryByText(/Preferred season/)).not.toBeInTheDocument()

    const bokChoy = within(requests.getByRole('heading', { name: 'Bok Choy' }).closest('li')!)
    expect(bokChoy.getByText('Cancelled')).toBeInTheDocument()
    expect(bokChoy.queryByRole('button')).not.toBeInTheDocument()
  })

  it('cancels an open request', async () => {
    const api = openCropRequests([buildCropRequest({ id: 4, crop_name: 'Okra' })])
    const user = userEvent.setup()
    const requests = await findSection('My crop requests')

    await user.click(await requests.findByRole('button', { name: 'Cancel request for Okra' }))

    expect(await requests.findByText('Cancelled')).toBeInTheDocument()
    expect(requests.queryByRole('button', { name: /Cancel request/ })).not.toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/crop-requests/4/cancel')).toHaveLength(1)
  })

  it('shows the server message when a cancellation is refused', async () => {
    const api = openCropRequests([buildCropRequest({ id: 4, crop_name: 'Okra' })])
    api.failNextRequest(
      'POST',
      '/api/crop-requests/4/cancel',
      409,
      'Only an open crop request can be cancelled',
    )
    const user = userEvent.setup()
    const requests = await findSection('My crop requests')

    await user.click(await requests.findByRole('button', { name: 'Cancel request for Okra' }))

    expect(await requests.findByRole('alert')).toHaveTextContent(
      'Only an open crop request can be cancelled',
    )
    expect(requests.getByText('Open')).toBeInTheDocument()
  })
})
