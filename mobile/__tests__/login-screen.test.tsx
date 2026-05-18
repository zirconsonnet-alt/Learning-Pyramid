import { fireEvent, render } from "@testing-library/react-native"

import { LoginScreen } from "../src/screens/LoginScreen"

describe("LoginScreen", () => {
  it("submits email and password", () => {
    const signIn = jest.fn()
    const screen = render(<LoginScreen signIn={signIn} loading={false} errorMessage={null} />)

    fireEvent.changeText(screen.getByPlaceholderText("邮箱"), "me@example.com")
    fireEvent.changeText(screen.getByPlaceholderText("密码"), "secret")
    fireEvent.press(screen.getByText("登录"))

    expect(signIn).toHaveBeenCalledWith("me@example.com", "secret")
  })
})
