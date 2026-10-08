import type { ReactNode } from 'react'

type FormCardProps = {
  title: string
  description: string
  children: ReactNode
}

export default function FormCard({ title, description, children }: FormCardProps) {
  return (
    <section className="mx-auto max-w-md rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
      <p className="mt-2 text-sm text-stone-600">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  )
}
