const marketplaceHighlights = [
  {
    title: 'Fresh local products',
    description: 'Vegetables, fruit, eggs, dairy and more from farms within the distance you choose.',
  },
  {
    title: 'Farm experiences',
    description: 'Pick-your-own days and farm tours hosted by the people who grow your food.',
  },
  {
    title: 'Grow-On-Demand',
    description: 'Ask for a crop you cannot find nearby and let local farmers plan a harvest around it.',
  },
]

export default function HomePage() {
  return (
    <>
      <section className="max-w-2xl">
        <h1 className="text-4xl font-bold tracking-tight text-green-900 sm:text-5xl">Farm2Local</h1>
        <p className="mt-4 text-lg leading-relaxed text-stone-700">
          A local agriculture marketplace connecting customers with nearby farms, fresh products
          and farm experiences.
        </p>
      </section>

      <ul className="mt-12 grid gap-4 sm:grid-cols-3">
        {marketplaceHighlights.map((highlight) => (
          <li
            key={highlight.title}
            className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm"
          >
            <h2 className="font-semibold text-stone-900">{highlight.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-stone-600">{highlight.description}</p>
          </li>
        ))}
      </ul>
    </>
  )
}
