import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { buildFarm, buildUser, installFakeApi } from '../test/fakeApi.ts'
import { renderApp } from '../test/renderApp.tsx'

const farmer = buildUser({ id: 7, name: 'Ben Fields', email: 'ben@example.com', role: 'FARMER' })
const farmerAccount = { user: farmer, password: 'tractor-barn-orchard' }
const existingFarm = buildFarm({ id: 3, owner_id: farmer.id })

function openDashboard(farms = [existingFarm]) {
  const api = installFakeApi({ accounts: [farmerAccount], farms })
  api.signIn(farmer)
  renderApp('/farmer')
  return api
}

async function fillRequiredFarmFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Farm name'), 'Sunny Meadow Farm')
  await user.type(screen.getByLabelText('Street address'), '42 Meadow Lane')
  await user.type(screen.getByLabelText('City'), 'Concord')
  await user.selectOptions(screen.getByLabelText('State'), 'North Carolina')
  await user.type(screen.getByLabelText('ZIP code'), '28025')
  await user.type(screen.getByLabelText('Latitude'), '35.4088')
  await user.type(screen.getByLabelText('Longitude'), '-80.5795')
}

describe('farmer without a farm', () => {
  it('explains what to do and offers to create a farm', async () => {
    openDashboard([])

    expect(
      await screen.findByRole('heading', { name: 'You have not set up your farm yet' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Farm' })).toBeInTheDocument()
  })

  it('creates a farm and then shows its profile', async () => {
    const api = openDashboard([])
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm' }))
    await fillRequiredFarmFields(user)
    await user.click(screen.getByRole('checkbox', { name: /Delivery available/ }))
    await user.click(screen.getByRole('button', { name: 'Create Farm' }))

    expect(await screen.findByRole('heading', { name: 'Sunny Meadow Farm' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Your farm has been created.')
    expect(screen.getByText('42 Meadow Lane, Concord, NC 28025')).toBeInTheDocument()
    expect(screen.getByText('Pickup and delivery')).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/farms')).toEqual([
      {
        method: 'POST',
        path: '/api/farms',
        body: {
          farm_name: 'Sunny Meadow Farm',
          description: null,
          address: '42 Meadow Lane',
          city: 'Concord',
          state: 'NC',
          zip_code: '28025',
          latitude: 35.4088,
          longitude: -80.5795,
          phone: null,
          pickup_available: true,
          delivery_available: true,
        },
      },
    ])
  })

  it('returns to the empty state when creation is cancelled', async () => {
    const api = openDashboard([])
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(
      screen.getByRole('heading', { name: 'You have not set up your farm yet' }),
    ).toBeInTheDocument()
    expect(api.requestsTo('POST', '/api/farms')).toHaveLength(0)
  })

  it.each([
    ['Latitude', '95', 'Latitude must be a number between -90 and 90.'],
    ['Longitude', '-190', 'Longitude must be a number between -180 and 180.'],
    ['Latitude', 'north', 'Latitude must be a number between -90 and 90.'],
  ])('rejects %s "%s" without calling the API', async (fieldLabel, value, expectedMessage) => {
    const api = openDashboard([])
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm' }))
    await fillRequiredFarmFields(user)
    await user.clear(screen.getByLabelText(fieldLabel))
    await user.type(screen.getByLabelText(fieldLabel), value)
    await user.click(screen.getByRole('button', { name: 'Create Farm' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(expectedMessage)
    expect(api.requestsTo('POST', '/api/farms')).toHaveLength(0)
  })

  it('shows the server message and keeps the form when saving fails', async () => {
    const api = openDashboard([])
    api.failNextRequest('POST', '/api/farms', 409, 'You already have a farm')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Create Farm' }))
    await fillRequiredFarmFields(user)
    await user.click(screen.getByRole('button', { name: 'Create Farm' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('You already have a farm')
    expect(screen.getByLabelText('Farm name')).toHaveValue('Sunny Meadow Farm')
    expect(screen.getByRole('button', { name: 'Create Farm' })).toBeEnabled()
  })
})

describe('farmer with a farm', () => {
  it('shows the farm profile', async () => {
    openDashboard()

    expect(await screen.findByRole('heading', { name: 'Green Acres' })).toBeInTheDocument()
    expect(screen.getByText('Family-run vegetable farm.')).toBeInTheDocument()
    expect(screen.getByText('100 Orchard Road, Charlotte, NC 28202')).toBeInTheDocument()
    expect(screen.getByText('35.2271, -80.8431')).toBeInTheDocument()
    expect(screen.getByText('704-555-0100')).toBeInTheDocument()
    expect(screen.getByText('Pickup only')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create Farm' })).not.toBeInTheDocument()
  })

  it('edits the farm and shows the saved changes', async () => {
    const api = openDashboard()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Edit Farm' }))
    expect(screen.getByLabelText('Farm name')).toHaveValue('Green Acres')
    expect(screen.getByLabelText('State')).toHaveValue('NC')
    expect(screen.getByLabelText('Latitude')).toHaveValue('35.2271')

    await user.clear(screen.getByLabelText('Farm name'))
    await user.type(screen.getByLabelText('Farm name'), 'Green Acres Organic')
    await user.clear(screen.getByLabelText('Phone'))
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('heading', { name: 'Green Acres Organic' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Your changes have been saved.')
    expect(screen.getByText('Not provided')).toBeInTheDocument()

    const [updateRequest] = api.requestsTo('PUT', '/api/farms/3')
    expect(updateRequest.body).toMatchObject({
      farm_name: 'Green Acres Organic',
      phone: null,
      latitude: 35.2271,
      longitude: -80.8431,
    })
  })

  it('discards changes when editing is cancelled', async () => {
    const api = openDashboard()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Edit Farm' }))
    await user.clear(screen.getByLabelText('Farm name'))
    await user.type(screen.getByLabelText('Farm name'), 'Abandoned Rename')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('heading', { name: 'Green Acres' })).toBeInTheDocument()
    expect(api.requestsTo('PUT', '/api/farms/3')).toHaveLength(0)
  })
})

describe('loading the farm', () => {
  it('shows an error with a retry that recovers', async () => {
    const api = openDashboard()
    api.failNextRequest('GET', '/api/farms/me', 500, 'Internal Server Error')
    const user = userEvent.setup()

    expect(await screen.findByRole('alert')).toHaveTextContent('Your farm could not be loaded.')

    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Green Acres' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('signs the farmer out when the session has expired', async () => {
    const api = openDashboard()
    api.failNextRequest('GET', '/api/farms/me', 401, 'Not authenticated')

    expect(await screen.findByRole('heading', { level: 1, name: 'Login' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Login' })).toBeInTheDocument()
  })
})
