import { render } from "@testing-library/react-native"

import RootLayout from "../src/app/_layout"

jest.mock("expo-router", () => {
  const React = require("react")
  const { Text, View } = require("react-native")
  function Stack({ children }: { children?: React.ReactNode }) {
    return React.createElement(
      View,
      null,
      React.createElement(Text, null, "MockStackNavigator"),
      children,
    )
  }
  Stack.Screen = ({ name, options }: { name: string; options?: { headerShown?: boolean; title?: string } }) =>
    React.createElement(
      React.Fragment,
      null,
      React.createElement(Text, null, `screen:${name}`),
      options?.headerShown === undefined
        ? null
        : React.createElement(Text, null, `screen:${name}:headerShown:${String(options.headerShown)}`),
      options?.title === undefined ? null : React.createElement(Text, null, `screen:${name}:title:${options.title}`),
    )

  return {
    Stack,
    Slot: () => React.createElement(Text, null, "MockSlotOutlet"),
  }
})

jest.mock("../src/api/ApiProvider", () => ({
  ApiProvider: ({ children }: { children: React.ReactNode }) => children,
}))

jest.mock("../src/auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

jest.mock("../src/auth/sessionStorage", () => ({
  secureSessionStorage: {
    clearSessionCookie: jest.fn(async () => undefined),
    getSessionCookie: jest.fn(async () => null),
    setSessionCookie: jest.fn(async () => undefined),
  },
}))

describe("RootLayout", () => {
  it("uses a native stack navigator so iOS edge-swipe back has a navigation stack", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("MockStackNavigator")).toBeTruthy()
    expect(screen.queryByText("MockSlotOutlet")).toBeNull()
  })

  it("registers project settings as an object-scoped route", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("screen:project-settings/[subjectId]/[scopedProjectId]")).toBeTruthy()
  })

  it("registers offline package management as a project-scoped route", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("screen:offline-packages/[subjectId]/[scopedProjectId]")).toBeTruthy()
  })

  it("hides the native project workbench header", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("screen:project/[subjectId]/[scopedProjectId]:headerShown:false")).toBeTruthy()
    expect(screen.queryByText("screen:project/[subjectId]/[scopedProjectId]:title:工作台")).toBeNull()
  })

  it("registers Mine as an account and system route", () => {
    const screen = render(<RootLayout />)

    expect(screen.getByText("screen:mine")).toBeTruthy()
  })
})
