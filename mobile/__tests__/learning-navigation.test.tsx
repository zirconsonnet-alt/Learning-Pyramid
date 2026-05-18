import { render } from "@testing-library/react-native"

import { ProjectScreen } from "../src/screens/ProjectScreen"

describe("ProjectScreen", () => {
  it("renders learning object titles", () => {
    const screen = render(
      <ProjectScreen
        loading={false}
        nodes={[
          { kind: "container", projectId: "p1", nodeId: "root", parentId: null, children: ["leaf"], title: "课程" },
          { kind: "leaf", projectId: "p1", nodeId: "leaf", parentId: "root", instanceId: "i1", title: "第一课" },
        ]}
        openNode={() => undefined}
      />,
    )

    expect(screen.getByText("课程")).toBeTruthy()
    expect(screen.getByText("第一课")).toBeTruthy()
  })

  it("renders a load error instead of an empty list", () => {
    const screen = render(<ProjectScreen errorMessage="加载失败" loading={false} nodes={[]} openNode={() => undefined} />)

    expect(screen.getByText("加载失败")).toBeTruthy()
  })
})
