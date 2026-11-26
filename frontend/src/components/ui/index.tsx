import { Component, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AlertCircle, CheckCircle2, X, Inbox } from 'lucide-react'

export function Alert({
  children,
  kind = 'info',
}: {
  children: ReactNode
  kind?: 'info' | 'error' | 'success'
}) {
  const Icon = kind === 'success' ? CheckCircle2 : AlertCircle
  return (
    <div className={`alert ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon size={18} />
      <div>{children}</div>
    </div>
  )
}
export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <Inbox size={32} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}
export function Skeleton() {
  return (
    <div aria-label="Loading results" role="status" className="skeleton">
      <span />
      <span />
      <span />
    </div>
  )
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close className="icon-button modal-close" aria-label="Close dialog">
            <X size={20} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
export function Badge({ children, status }: { children: ReactNode; status?: string }) {
  return <span className={`badge ${status || ''}`}>{children}</span>
}
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <main className="standalone">
        <h1>This page could not load</h1>
        <p>Your last change may not have been saved.</p>
        <button onClick={() => window.location.assign('/')}>Return home</button>
      </main>
    ) : (
      this.props.children
    )
  }
}
