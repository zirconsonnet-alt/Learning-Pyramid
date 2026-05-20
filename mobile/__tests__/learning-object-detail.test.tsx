import { render } from "@testing-library/react-native"
import { useVideoPlayer } from "expo-video"
import { Text } from "react-native"

import { ApiProvider, useApiRuntime } from "../src/api/ApiProvider"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { InstanceSubtitleFile } from "../src/api/subtitles"
import type { createLearningPyramidApi } from "../src/api/types"
import { getLocalPackagePlaybackDescriptor } from "../src/offlineCoursePackages/source"
import { LearningMediaPlayer } from "../src/screens/LearningMediaPlayer"
import { LearningObjectScreen } from "../src/screens/LearningObjectScreen"

type TimeUpdateHandler = (payload: { currentTime: number }) => void

const mockPlayer = {
  id: "player",
  timeUpdateEventInterval: 0,
  addListener: jest.fn((_eventName: "timeUpdate", handler: TimeUpdateHandler) => {
    mockPlayer.timeUpdateHandler = handler
    return { remove: jest.fn() }
  }),
  timeUpdateHandler: null as TimeUpdateHandler | null,
}

jest.mock("expo-video", () => {
  const React = require("react")
  const { Text } = require("react-native")
  return {
    useVideoPlayer: jest.fn(() => mockPlayer),
    VideoView: () => React.createElement(Text, null, "VideoView"),
  }
})

const playableDescriptor: PlaybackDescriptor = {
  instanceId: "inst_1",
  sourceKind: "SERVER_FS",
  playbackKind: "FILE",
  url: "/api/subjects/subj_1/projects/proj_1/media/instances/inst_1",
  mimeType: "video/mp4",
  durationMs: 120000,
  supportsFrameGrab: true,
  supportsServerAsr: true,
}

const subtitleFile: InstanceSubtitleFile = {
  found: true,
  instanceId: "inst_1",
  fileName: "lesson.srt",
  format: "srt",
  source: "UPLOADED",
  segments: [
    { startMs: 1000, endMs: 3000, text: "当前字幕" },
    { startMs: 4000, endMs: 5000, text: "后一句" },
  ],
}

const leafNode: LearningObjectNode = {
  kind: "leaf",
  projectId: "proj_1",
  nodeId: "node_1",
  parentId: null,
  instanceId: "inst_1",
  title: "第一课",
}

const recallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_1",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "学习金字塔强调什么？" }],
  answer: [{ kind: "TEXT", text: "主动回忆和应用。" }],
  anchor: { instanceId: "inst_1", position: "t=10000" },
  references: [],
  insights: [],
}

describe("LearningMediaPlayer", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockPlayer.timeUpdateEventInterval = 0
    mockPlayer.timeUpdateHandler = null
  })

  it("passes resolved URL and session cookie header to expo-video for supported playback", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={playableDescriptor}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(screen.getByText("VideoView")).toBeTruthy()
    expect(useVideoPlayer).toHaveBeenCalledWith(
      expect.objectContaining({
        contentType: "progressive",
        headers: { Cookie: "plm_session=abc" },
        metadata: { title: "第一课" },
        uri: "https://plm.xuebao.chat/api/subjects/subj_1/projects/proj_1/media/instances/inst_1",
      }),
    )
  })

  it("reports playback time updates in milliseconds", () => {
    const onPlaybackTimeChange = jest.fn()
    render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={playableDescriptor}
        loading={false}
        onPlaybackTimeChange={onPlaybackTimeChange}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(mockPlayer.timeUpdateEventInterval).toBe(0.5)
    expect(mockPlayer.addListener).toHaveBeenCalledWith("timeUpdate", expect.any(Function))

    mockPlayer.timeUpdateHandler?.({ currentTime: 12.345 })
    expect(onPlaybackTimeChange).toHaveBeenCalledWith(12345)
  })

  it("overlays the current subtitle segment from the shared subtitle file", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={1500}
        descriptor={playableDescriptor}
        loading={false}
        sessionCookie="plm_session=abc"
        subtitleFile={subtitleFile}
        title="第一课"
      />,
    )

    expect(screen.getByText("当前字幕")).toBeTruthy()
    expect(screen.queryByText("后一句")).toBeNull()
  })

  it("shows an explicit unsupported state for desktop native media", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={{ ...playableDescriptor, sourceKind: "NATIVE_LOCAL" }}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(screen.getByText("移动端不支持桌面本地媒体")).toBeTruthy()
    expect(useVideoPlayer).not.toHaveBeenCalled()
  })

  it("hides Baidu Netdisk playback on mobile", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={{ ...playableDescriptor, sourceKind: "BAIDU_NETDISK", playbackKind: "HLS", url: "/baidu.m3u8" }}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(screen.getByText("当前媒体源已隐藏，请改用本地素材。")).toBeTruthy()
    expect(useVideoPlayer).not.toHaveBeenCalled()
  })

  it("uses file URLs directly for verified local package playback", () => {
    render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={{ ...playableDescriptor, sourceKind: "LOCAL_COURSE_PACKAGE", url: "file://document/courses/pkg_1/videos/01.mp4" }}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(useVideoPlayer).toHaveBeenCalledWith(
      expect.objectContaining({
        headers: undefined,
        uri: "file://document/courses/pkg_1/videos/01.mp4",
      }),
    )
  })
})

describe("local package playback source", () => {
  it("resolves a verified local package item into a local playback descriptor", () => {
    const descriptor = getLocalPackagePlaybackDescriptor({
      instanceId: "inst_1",
      item: {
        itemId: "lesson_1",
        title: "第一讲",
        order: 1,
        learningObjectKey: "inst_1",
        video: { path: "videos/01.mp4", sizeBytes: 10, sha256: "0".repeat(64) },
      },
      packageRootUri: "file://document/courses/pkg_1",
    })

    expect(descriptor.sourceKind).toBe("LOCAL_COURSE_PACKAGE")
    expect(descriptor.url).toBe("file://document/courses/pkg_1/videos/01.mp4")
  })
})

describe("ApiProvider", () => {
  it("exposes API base URL and the current session cookie reader", () => {
    const api = {} as ReturnType<typeof createLearningPyramidApi>

    function Probe() {
      const runtime = useApiRuntime()
      return <Text>{`${runtime.apiBaseUrl}|${runtime.getSessionCookie()}`}</Text>
    }

    const screen = render(
      <ApiProvider api={api} apiBaseUrl="https://plm.xuebao.chat/api" getSessionCookie={() => "plm_session=abc"}>
        <Probe />
      </ApiProvider>,
    )

    expect(screen.getByText("https://plm.xuebao.chat/api|plm_session=abc")).toBeTruthy()
  })
})

describe("LearningObjectScreen", () => {
  it("renders learning object title, media, and recall points", () => {
    const screen = render(
      <LearningObjectScreen
        apiBaseUrl="https://plm.xuebao.chat/api"
        node={leafNode}
        nodeErrorMessage={null}
        nodeLoading={false}
        playback={playableDescriptor}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[recallPoint]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        sessionCookie="plm_session=abc"
      />,
    )

    expect(screen.getByText("第一课")).toBeTruthy()
    expect(screen.getByText("VideoView")).toBeTruthy()
    expect(screen.getByText("学习金字塔强调什么？")).toBeTruthy()
    expect(screen.getByText("主动回忆和应用。")).toBeTruthy()
  })
})
