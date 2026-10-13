import type { CropPoll } from '../../api/cropPolls.ts'

type PollResultsProps = {
  poll: CropPoll
  /** The option the viewer voted for, if any, which is marked in the list. */
  chosenOptionId?: number
}

function describeVotes(votes: number): string {
  return `${votes} ${votes === 1 ? 'vote' : 'votes'}`
}

/** Each option of a poll with its vote count and share of the total. */
export default function PollResults({ poll, chosenOptionId }: PollResultsProps) {
  return (
    <ul className="space-y-2">
      {poll.options.map((option) => {
        const percent = poll.total_votes === 0 ? 0 : (option.votes / poll.total_votes) * 100
        return (
          <li key={option.id}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium text-stone-900">
                {option.crop_name}
                {option.id === chosenOptionId && (
                  <span className="ml-2 text-xs font-normal text-green-800">Your vote</span>
                )}
              </span>
              <span className="text-stone-600">{describeVotes(option.votes)}</span>
            </div>
            <div
              role="progressbar"
              aria-label={`Share of votes for ${option.crop_name}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(percent)}
              className="mt-1 h-2 overflow-hidden rounded-full bg-stone-200"
            >
              <div className="h-full rounded-full bg-green-700" style={{ width: `${percent}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
