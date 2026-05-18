import { StyleSheet, View } from "react-native"
import { VideoView, useVideoPlayer, type ContentType, type VideoSource } from "expo-video"

import { buildCookieHeader } from "../auth/sessionCookie"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { resolveApiResourceUrl } from "../api/http"
import type { PlaybackDescriptor } from "../api/media"

export function LearningMediaPlayer({
  apiBaseUrl,
  descriptor,
  errorMessage,
  loading,
  sessionCookie,
  title,
}: {
  apiBaseUrl: string
  descriptor: PlaybackDescriptor | null
  errorMessage?: string | null
  loading: boolean
  sessionCookie?: string | null
  title: string
}) {
  if (loading) return <LoadingState label="加载媒体" />
  if (errorMessage) return <EmptyState title={errorMessage} />
  if (!descriptor) return <EmptyState title="暂无媒体" />

  const unsupportedMessage = getUnsupportedPlaybackMessage(descriptor)
  if (unsupportedMessage) return <EmptyState title={unsupportedMessage} />

  const cookieHeader = buildCookieHeader(sessionCookie)
  const source: VideoSource = {
    uri: resolveApiResourceUrl(apiBaseUrl, descriptor.url),
    contentType: descriptor.playbackKind === "HLS" ? ("hls" satisfies ContentType) : ("progressive" satisfies ContentType),
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
    metadata: { title },
  }

  return <PlayableVideo source={source} />
}

function getUnsupportedPlaybackMessage(descriptor: PlaybackDescriptor) {
  if (descriptor.sourceKind === "NATIVE_LOCAL") return "移动端不支持桌面本地媒体"
  if (descriptor.sourceKind === "BROWSER_LOCAL") return "移动端不支持浏览器本地媒体"
  if (descriptor.sourceKind === "MANUAL") return "当前媒体没有可播放文件"
  if (!descriptor.url.trim()) return "当前媒体没有可播放地址"
  return null
}

function PlayableVideo({ source }: { source: VideoSource }) {
  const player = useVideoPlayer(source)
  return (
    <View style={styles.shell}>
      <VideoView contentFit="contain" nativeControls player={player} style={styles.video} />
    </View>
  )
}

const styles = StyleSheet.create({
  shell: { backgroundColor: "#020617", borderRadius: 8, overflow: "hidden" },
  video: { aspectRatio: 16 / 9, width: "100%" },
})
