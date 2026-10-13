import { apiRequest } from './client.ts'

export type CropPollStatus = 'OPEN' | 'CLOSED'

export type CropPollOption = { id: number; crop_name: string; votes: number }

export type CropPoll = {
  id: number
  farm_id: number
  question: string
  status: CropPollStatus
  created_at: string
  options: CropPollOption[]
  total_votes: number
}

export type NewCropPoll = { question: string; options: string[] }

export type CropPollSearchResult = {
  poll: CropPoll
  farm: { id: number; farm_name: string; city: string; state: string }
  distance_miles: number
}

/** Which option the signed-in customer chose in a poll. */
export type CropVote = { poll_id: number; option_id: number }

/** A vote that was just cast, with the poll's updated counts. */
export type CropVoteResult = CropVote & { poll: CropPoll }

export function createCropPoll(accessToken: string, poll: NewCropPoll): Promise<CropPoll> {
  return apiRequest<CropPoll>('/api/crop-polls', { method: 'POST', body: poll, accessToken })
}

export function fetchMyCropPolls(accessToken: string): Promise<CropPoll[]> {
  return apiRequest<CropPoll[]>('/api/crop-polls/mine', { accessToken })
}

export function closeCropPoll(accessToken: string, pollId: number): Promise<CropPoll> {
  return apiRequest<CropPoll>(`/api/crop-polls/${pollId}/close`, { method: 'POST', accessToken })
}

export function searchCropPolls(criteria: {
  latitude: number
  longitude: number
  radiusMiles: number
}): Promise<CropPollSearchResult[]> {
  const params = new URLSearchParams({
    latitude: String(criteria.latitude),
    longitude: String(criteria.longitude),
    radius_miles: String(criteria.radiusMiles),
  })
  return apiRequest<CropPollSearchResult[]>(`/api/crop-polls/search?${params}`)
}

export function castCropVote(
  accessToken: string,
  pollId: number,
  optionId: number,
): Promise<CropVoteResult> {
  return apiRequest<CropVoteResult>('/api/crop-votes', {
    method: 'POST',
    body: { poll_id: pollId, option_id: optionId },
    accessToken,
  })
}

export function fetchMyCropVotes(accessToken: string): Promise<CropVote[]> {
  return apiRequest<CropVote[]>('/api/crop-votes/mine', { accessToken })
}
