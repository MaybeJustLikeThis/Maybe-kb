import { reactive } from 'vue'

export interface TopBarAction {
  label: string
  onClick: () => void
  btnClass: string
  disabled?: boolean
}

export interface TopBarState {
  backTo: string
  title?: string
  actions: TopBarAction[]
}

const state = reactive<{ current: TopBarState | null }>({
  current: null,
})

export function setTopBar(tb: TopBarState | null) {
  state.current = tb
}

export function useTopBar() {
  return state
}
