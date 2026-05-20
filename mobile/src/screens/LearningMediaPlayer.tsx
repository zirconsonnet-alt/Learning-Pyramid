import { useEffect } from "react"
import { StyleSheet, Text, View } from "react-native"
import { VideoView, useVideoPlayer, type ContentType, type VideoSource } from "expo-video"

import { buildCookieHeader } from "../auth/sessionCookie"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { ui } from "../constants/ui"
import { resolveApiResourceUrl } from "../api/http"
import type { PlaybackDescriptor } from "../api/media"
import type { InstanceSubtitleFile } from "../api/subtitles"

export function LearningMediaPlayer({
  apiBaseUrl,
  currentMs = 0,
  descriptor,
  errorMessage,
  loading,
  onPlaybackTimeChange,
  sessionCookie,
  subtitleFile,
  title,
}: {
  apiBaseUrl: string
  currentMs?: number
  descriptor: PlaybackDescriptor | null
  errorMessage?: string | null
  loading: boolean
  onPlaybackTimeChange?: (currentMs: number) => void
  sessionCookie?: string | null
  subtitleFile?: InstanceSubtitleFile | null
  title: string
}) {
  if (loading) return <LoadingState label="加载媒体" />
  if (errorMessage) return <EmptyState title={errorMessage} />
  if (!descriptor) return <MediaUnavailableState title="暂无媒体" />

  const unsupportedMessage = getUnsupportedPlaybackMessage(descriptor)
  if (unsupportedMessage) return <MediaUnavailableState title={unsupportedMessage} />

  const cookieHeader = buildCookieHeader(sessionCookie)
  const sourceUri =
    descriptor.sourceKind === "LOCAL_COURSE_PACKAGE"
      ? descriptor.url
      : resolveApiResourceUrl(apiBaseUrl, descriptor.url)
  const source: VideoSource = {
    uri: sourceUri,
    contentType: descriptor.playbackKind === "HLS" ? ("hls" satisfies ContentType) : ("progressive" satisfies ContentType),
    headers: descriptor.sourceKind === "LOCAL_COURSE_PACKAGE" ? undefined : cookieHeader ? { Cookie: cookieHeader } : undefined,
    metadata: { title },
  }

  return <PlayableVideo onPlaybackTimeChange={onPlaybackTimeChange} source={source} subtitleText={findSubtitleText(subtitleFile, currentMs)} />
}

function MediaUnavailableState({ title }: { title: string }) {
  return (
    <View style={styles.unavailableShell}>
      <View style={styles.mediaIllustration} pointerEvents="none">
        <View style={styles.windowFrame}>
          <View style={styles.windowHeader}>
            <View style={styles.windowDot} />
            <View style={styles.windowDot} />
            <View style={styles.windowDot} />
          </View>
          <View style={styles.lockBody}>
            <View style={styles.lockShackle} />
            <View style={styles.lockBox}>
              <View style={styles.lockKeyhole} />
            </View>
          </View>
        </View>
        <View style={styles.cloudShape} />
      </View>
      <View style={styles.unavailableCopy}>
        <Text maxFontSizeMultiplier={1.1} style={styles.unavailableTitle}>{title}</Text>
      </View>
    </View>
  )
}

function getUnsupportedPlaybackMessage(descriptor: PlaybackDescriptor) {
  if (descriptor.sourceKind === "NATIVE_LOCAL") return "移动端不支持桌面本地媒体"
  if (descriptor.sourceKind === "BROWSER_LOCAL") return "移动端不支持浏览器本地媒体"
  if (descriptor.sourceKind === "BAIDU_NETDISK") return "当前媒体源已隐藏，请改用本地素材。"
  if (descriptor.sourceKind === "MANUAL") return "当前媒体没有可播放文件"
  if (descriptor.sourceKind === "LOCAL_COURSE_PACKAGE" && !descriptor.url.startsWith("file://")) return "本地课程包文件地址无效"
  if (!descriptor.url.trim()) return "当前媒体没有可播放地址"
  return null
}

function PlayableVideo({
  onPlaybackTimeChange,
  source,
  subtitleText,
}: {
  onPlaybackTimeChange?: (currentMs: number) => void
  source: VideoSource
  subtitleText: string | null
}) {
  const player = useVideoPlayer(source)

  useEffect(() => {
    if (!onPlaybackTimeChange) return

    player.timeUpdateEventInterval = 0.5
    const subscription = player.addListener("timeUpdate", ({ currentTime }) => {
      if (!Number.isFinite(currentTime)) return
      onPlaybackTimeChange(Math.max(0, Math.floor(currentTime * 1000)))
    })

    return () => {
      subscription.remove()
      player.timeUpdateEventInterval = 0
    }
  }, [onPlaybackTimeChange, player])

  return (
    <View style={styles.shell}>
      <VideoView contentFit="contain" nativeControls player={player} style={styles.video} />
      {subtitleText ? (
        <View pointerEvents="none" style={styles.subtitleOverlay}>
          <Text style={styles.subtitleText}>{subtitleText}</Text>
        </View>
      ) : null}
    </View>
  )
}

function findSubtitleText(subtitleFile: InstanceSubtitleFile | null | undefined, currentMs: number) {
  if (!subtitleFile?.found) return null
  const playbackMs = Math.max(0, Math.floor(Number.isFinite(currentMs) ? currentMs : 0))
  const segment = subtitleFile.segments.find((item) => playbackMs >= item.startMs && playbackMs < item.endMs)
  return segment?.text.trim() || null
}

const styles = StyleSheet.create({
  shell: {
    backgroundColor: ui.colors.videoShell,
    borderRadius: ui.radius.md,
    overflow: "hidden",
    position: "relative",
  },
  cloudShape: {
    backgroundColor: "#c5ccff",
    borderRadius: 28,
    bottom: 8,
    height: 52,
    opacity: 0.82,
    position: "absolute",
    right: 0,
    width: 76,
  },
  lockBody: { alignItems: "center", flex: 1, justifyContent: "center" },
  lockBox: {
    alignItems: "center",
    backgroundColor: "#6271f6",
    borderRadius: ui.radius.sm,
    height: 40,
    justifyContent: "center",
    marginTop: -4,
    width: 44,
  },
  lockKeyhole: { backgroundColor: ui.colors.surface, borderRadius: 4, height: 10, opacity: 0.9, width: 8 },
  lockShackle: {
    borderColor: "#6271f6",
    borderRadius: 18,
    borderWidth: 6,
    height: 38,
    width: 34,
  },
  mediaIllustration: { height: 116, width: 160 },
  subtitleOverlay: {
    alignItems: "center",
    bottom: 10,
    left: 8,
    position: "absolute",
    right: 8,
  },
  subtitleText: {
    backgroundColor: "rgba(2, 6, 23, 0.76)",
    borderRadius: ui.radius.sm,
    color: ui.colors.secondaryBackground,
    fontSize: ui.type.control,
    lineHeight: 21,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 4,
    textAlign: "center",
  },
  video: { aspectRatio: 16 / 9, width: "100%" },
  unavailableCopy: { flex: 1, minWidth: 150 },
  unavailableShell: {
    alignItems: "center",
    backgroundColor: ui.colors.surface,
    borderColor: "#cbd3fb",
    borderRadius: ui.radius.xl,
    borderWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: ui.spacing.xl,
    minHeight: 146,
    paddingHorizontal: ui.spacing.xl,
    paddingVertical: ui.spacing.xl,
  },
  unavailableTitle: { color: ui.colors.text, fontSize: 20, fontWeight: "800", lineHeight: 30 },
  windowDot: { backgroundColor: ui.colors.surface, borderRadius: 3, height: 6, width: 6 },
  windowFrame: {
    backgroundColor: "#eef1ff",
    borderColor: "#aeb8ff",
    borderRadius: ui.radius.xl,
    borderWidth: 2,
    height: 96,
    overflow: "hidden",
    width: 126,
  },
  windowHeader: {
    backgroundColor: "#7583f8",
    flexDirection: "row",
    gap: 7,
    height: 22,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
})
