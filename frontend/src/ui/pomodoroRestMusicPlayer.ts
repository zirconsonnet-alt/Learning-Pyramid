export type PomodoroRestMusicPlayerState = {
  currentTrackPath: string
  isPlaying: boolean
  isRestPhaseActive: boolean
}

type Listener = () => void

export const pomodoroRestMusicState: PomodoroRestMusicPlayerState = {
  currentTrackPath: "",
  isPlaying: false,
  isRestPhaseActive: false,
}

let audio: HTMLAudioElement | null = null
let objectUrl = ""
const listeners = new Set<Listener>()

function emitPomodoroRestMusicPlayerChange() {
  listeners.forEach((listener) => listener())
}

function setPomodoroRestMusicState(nextState: Partial<PomodoroRestMusicPlayerState>) {
  Object.assign(pomodoroRestMusicState, nextState)
  emitPomodoroRestMusicPlayerChange()
}

function revokePomodoroRestMusicObjectUrl() {
  if (!objectUrl) return
  URL.revokeObjectURL(objectUrl)
  objectUrl = ""
}

export function getPomodoroRestMusicPlayerSnapshot(): PomodoroRestMusicPlayerState {
  return { ...pomodoroRestMusicState }
}

export function subscribePomodoroRestMusicPlayer(listener: Listener) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function setPomodoroRestMusicPhaseActive(isRestPhaseActive: boolean) {
  setPomodoroRestMusicState({ isRestPhaseActive })
  if (!isRestPhaseActive) {
    pausePomodoroRestMusic()
  }
}

export async function playPomodoroRestMusicTrack(relativePath: string, file: File) {
  const normalizedPath = relativePath.trim()
  if (!normalizedPath) return false
  const nextAudio = audio ?? new Audio()
  audio = nextAudio
  nextAudio.pause()
  revokePomodoroRestMusicObjectUrl()
  objectUrl = URL.createObjectURL(file)
  nextAudio.src = objectUrl
  nextAudio.preload = "auto"
  nextAudio.onended = () => setPomodoroRestMusicState({ isPlaying: false })
  nextAudio.onerror = () => setPomodoroRestMusicState({ isPlaying: false })
  await nextAudio.play()
  setPomodoroRestMusicState({
    currentTrackPath: normalizedPath,
    isPlaying: true,
  })
  return true
}

export function pausePomodoroRestMusic() {
  audio?.pause()
  setPomodoroRestMusicState({ isPlaying: false })
}
