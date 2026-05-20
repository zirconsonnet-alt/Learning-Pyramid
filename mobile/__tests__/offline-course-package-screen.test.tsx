import { fireEvent, render } from "@testing-library/react-native"

import { OfflineCoursePackagesScreen } from "../src/screens/OfflineCoursePackagesScreen"

describe("OfflineCoursePackagesScreen", () => {
  it("shows local package management actions without claiming system file access", () => {
    const connectComputer = jest.fn()
    const screen = render(
      <OfflineCoursePackagesScreen
        connectComputer={connectComputer}
        packages={[]}
        projectTitle="默认网课材料"
      />,
    )

    expect(screen.getByText("离线课程包")).toBeTruthy()
    expect(screen.getByText("默认网课材料")).toBeTruthy()
    expect(screen.getByText("连接电脑")).toBeTruthy()
    expect(screen.queryByText("扫描手机文件")).toBeNull()
    fireEvent.press(screen.getByText("连接电脑"))
    expect(connectComputer).toHaveBeenCalled()
  })
})
