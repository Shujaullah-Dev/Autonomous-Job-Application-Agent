import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  type Dispatch,
  type SetStateAction,
} from 'react'
import { seed, type DemoState } from '../lib/demo'

const Context = createContext<{
  state: DemoState
  setState: Dispatch<SetStateAction<DemoState>>
  reset: () => void
} | null>(null)
export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(seed)
  return (
    <Context.Provider value={{ state, setState, reset: () => setState(seed()) }}>
      {children}
    </Context.Provider>
  )
}
export function useDemo() {
  const value = useContext(Context)
  if (!value) throw new Error('Demo provider is missing')
  return value
}
