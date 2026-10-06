import type { ReactNode } from 'react'

type PlaceholderPageProps = {
  title: string
  description: string
  children?: ReactNode
}

export default function PlaceholderPage({ title, description, children }: PlaceholderPageProps) {
  return (
    <section className="mx-auto max-w-xl rounded-xl border border-stone-200 bg-white p-8 text-center shadow-sm">
      <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
      <p className="mt-3 text-stone-600">{description}</p>
      {children && <div className="mt-6">{children}</div>}
    </section>
  )
}
