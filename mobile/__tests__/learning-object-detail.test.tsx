import { render } from "@testing-library/react-native"
import { useVideoPlayer } from "expo-video"
import { Text } from "react-native"

import { ApiProvider, useApiRuntime } from "../src/api/ApiProvider"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { createLearningPyramidApi } from "../src/api/types"
import { LearningMediaPlayer } from "../src/screens/LearningMediaPlayer"
import { LearningObjectScreen } from "../src/screens/LearningObjectScreen"

jest.mock("expo-video", () => {
  const React = require("react")
  const { Text } = require("react-native")
  return {
    useVideoPlayer: jest.fn(() => ({ id: "player" })),
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
  anchor: { instanceId: "inst_1", position: "00:00:10" },
  references: [],
  insights: [],
}

describe("LearningMediaPlayer", () => {
  beforeEach(() => {
    jest.clearAllMocks()
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
