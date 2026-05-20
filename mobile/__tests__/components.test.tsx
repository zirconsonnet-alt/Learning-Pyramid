import { AppButton } from "../src/components/AppButton"
import { EmptyState } from "../src/components/EmptyState"
import { LoadingState } from "../src/components/LoadingState"
import { renderWithProviders } from "../src/test/renderWithProviders"
import { StyleSheet } from "react-native"

describe("mobile base components", () => {
  it("renders concise loading and empty states", () => {
    const loading = renderWithProviders(<LoadingState label="加载中" />)
    expect(loading.getByText("加载中")).toBeTruthy()

    const empty = renderWithProviders(<EmptyState title="暂无内容" />)
    expect(empty.getByText("暂无内容")).toBeTruthy()
  })

  it("renders a button label without web-only elements", () => {
    const button = renderWithProviders(<AppButton label="进入" onPress={() => undefined} />)
    expect(button.getByText("进入")).toBeTruthy()
  })

  it("exposes disabled button state to accessibility", () => {
    const button = renderWithProviders(
      <AppButton disabled label="进入" onPress={() => undefined} />,
    )

    expect(button.toJSON()).toMatchObject({
      props: { accessibilityState: { disabled: true } },
    })
  })

  it("renders secondary buttons as lighter actions", () => {
    const button = renderWithProviders(<AppButton label="内容目录" onPress={() => undefined} variant="secondary" />)
    const node = button.toJSON()

    expect(StyleSheet.flatten(node?.props.style)).toEqual(
      expect.objectContaining({
        backgroundColor: "#f8fafc",
        borderColor: "#d6dbe3",
        borderWidth: 1,
      }),
    )
  })

  it("keeps button labels from exploding under Android font scaling", () => {
    const button = renderWithProviders(<AppButton label="复述点录入" onPress={() => undefined} />)

    expect(button.getByText("复述点录入").props.maxFontSizeMultiplier).toBeLessThanOrEqual(1.1)
  })
})
