import { fireEvent } from "@testing-library/react-native"

import { GlobalSettingsScreen } from "../src/screens/GlobalSettingsScreen"
import { SubjectSettingsScreen } from "../src/screens/SubjectSettingsScreen"
import { SubjectMaterialsScreen } from "../src/screens/SubjectMaterialsScreen"
import { SubjectsScreen } from "../src/screens/SubjectsScreen"
import { renderWithProviders } from "../src/test/renderWithProviders"

describe("mobile infrastructure screens", () => {
  it("lets the subject center create subjects, open settings, and request delete confirmation", () => {
    const createSubject = jest.fn()
    const deleteSubject = jest.fn()
    const openGlobalSettings = jest.fn()
    const openSubjectSettings = jest.fn()

    const screen = renderWithProviders(
      <SubjectsScreen
        loading={false}
        subjects={[
          {
            subjectId: "subj_1",
            title: "数学",
            state: "ACTIVE",
            createdAt: "2026-05-19T00:00:00Z",
            deletedAt: null,
          },
        ]}
        openSubject={() => undefined}
        openSubjectSettings={openSubjectSettings}
        openGlobalSettings={openGlobalSettings}
        createSubject={createSubject}
        deleteSubject={deleteSubject}
        signOut={() => undefined}
      />,
    )

    fireEvent.press(screen.getByText("全局设置"))
    expect(openGlobalSettings).toHaveBeenCalled()

    fireEvent.press(screen.getByText("设置"))
    expect(openSubjectSettings).toHaveBeenCalledWith("subj_1")

    fireEvent.changeText(screen.getByPlaceholderText("新学科名称"), "英语")
    fireEvent.press(screen.getByText("新建学科"))
    expect(createSubject).toHaveBeenCalledWith("英语")

    expect(screen.queryByPlaceholderText("输入学科名称删除")).toBeNull()
    fireEvent.press(screen.getByText("删除"))
    fireEvent.changeText(screen.getByPlaceholderText("输入学科名称删除"), "数学")
    fireEvent.press(screen.getByText("删除学科"))
    expect(deleteSubject).toHaveBeenCalledWith("subj_1")
  })

  it("lets the project center create and delete subject materials", () => {
    const createMaterial = jest.fn()
    const deleteMaterial = jest.fn()

    const screen = renderWithProviders(
      <SubjectMaterialsScreen
        loading={false}
        materials={[
          {
            subjectId: "subj_1",
            materialId: "mat_1",
            materialType: "COURSE",
            title: "第一课",
            createdAt: "2026-05-19T00:00:00Z",
            scopedProjectId: "proj_1",
          },
        ]}
        openMaterial={() => undefined}
        createMaterial={createMaterial}
        deleteMaterial={deleteMaterial}
      />,
    )

    fireEvent.changeText(screen.getByPlaceholderText("新项目名称"), "线性代数")
    fireEvent.press(screen.getByText("书籍"))
    fireEvent.press(screen.getByText("新建项目"))
    expect(createMaterial).toHaveBeenCalledWith({ materialType: "BOOK", title: "线性代数" })

    expect(screen.queryByPlaceholderText("输入项目名称删除")).toBeNull()
    fireEvent.press(screen.getByText("删除"))
    fireEvent.changeText(screen.getByPlaceholderText("输入项目名称删除"), "第一课")
    fireEvent.press(screen.getByText("删除项目"))
    expect(deleteMaterial).toHaveBeenCalledWith("mat_1")
  })

  it("lets subject settings rename the subject", () => {
    const saveTitle = jest.fn()
    const screen = renderWithProviders(
      <SubjectSettingsScreen
        loading={false}
        subject={{
          subjectId: "subj_1",
          title: "数学",
          state: "ACTIVE",
          createdAt: "2026-05-19T00:00:00Z",
          deletedAt: null,
        }}
        saveTitle={saveTitle}
      />,
    )

    fireEvent.changeText(screen.getByPlaceholderText("学科名称"), "高等数学")
    fireEvent.press(screen.getByText("保存学科"))

    expect(saveTitle).toHaveBeenCalledWith("高等数学")
  })

  it("lets global settings save user services and theme", () => {
    const saveLlmSettings = jest.fn()
    const clearLlmApiKey = jest.fn()
    const saveAsrSettings = jest.fn()
    const clearAsrApiKey = jest.fn()
    const saveTheme = jest.fn()

    const screen = renderWithProviders(
      <GlobalSettingsScreen
        loading={false}
        llmSettings={{
          baseUrl: "https://llm.example.com/v1",
          modelName: "gpt-test",
          promptAssemblyMode: "system",
          savedApiKeyConfigured: true,
          savedApiKeyPreview: "sk-***",
          llmConfigured: true,
          storyGenerationConfigured: true,
          llmSource: "user",
        }}
        asrSettings={{
          baseUrl: "https://asr.example.com/v1",
          modelName: "asr-test",
          savedApiKeyConfigured: false,
          savedApiKeyPreview: null,
          asrConfigured: true,
          asrSource: "user",
        }}
        globalSettings={{
          theme: "light",
          updatedAt: null,
        }}
        saveLlmSettings={saveLlmSettings}
        clearLlmApiKey={clearLlmApiKey}
        saveAsrSettings={saveAsrSettings}
        clearAsrApiKey={clearAsrApiKey}
        saveTheme={saveTheme}
      />,
    )

    fireEvent.changeText(screen.getByPlaceholderText("LLM Base URL"), "https://new-llm.example.com/v1")
    fireEvent.changeText(screen.getByPlaceholderText("LLM 模型名"), "gpt-new")
    fireEvent.changeText(screen.getByPlaceholderText("LLM API Key"), "sk-new")
    fireEvent.press(screen.getByText("保存大模型"))
    expect(saveLlmSettings).toHaveBeenCalledWith({
      baseUrl: "https://new-llm.example.com/v1",
      modelName: "gpt-new",
      apiKey: "sk-new",
      promptAssemblyMode: "system",
    })

    fireEvent.press(screen.getByText("清除大模型密钥"))
    expect(clearLlmApiKey).toHaveBeenCalled()

    fireEvent.changeText(screen.getByPlaceholderText("ASR Base URL"), "https://new-asr.example.com/v1")
    fireEvent.changeText(screen.getByPlaceholderText("ASR 模型名"), "asr-new")
    fireEvent.changeText(screen.getByPlaceholderText("ASR API Key"), "asr-key")
    fireEvent.press(screen.getByText("保存语音识别"))
    expect(saveAsrSettings).toHaveBeenCalledWith({
      baseUrl: "https://new-asr.example.com/v1",
      modelName: "asr-new",
      apiKey: "asr-key",
    })

    fireEvent.press(screen.getByText("清除语音识别密钥"))
    expect(clearAsrApiKey).toHaveBeenCalled()

    fireEvent.press(screen.getByText("深色"))
    expect(saveTheme).toHaveBeenCalledWith("dark")
  })

  it("does not send an empty service api key when saving existing settings", () => {
    const saveLlmSettings = jest.fn()
    const saveAsrSettings = jest.fn()

    const screen = renderWithProviders(
      <GlobalSettingsScreen
        loading={false}
        llmSettings={{
          baseUrl: "https://llm.example.com/v1",
          modelName: "gpt-test",
          promptAssemblyMode: "system",
          savedApiKeyConfigured: true,
          savedApiKeyPreview: "sk-***",
          llmConfigured: true,
          storyGenerationConfigured: true,
          llmSource: "user",
        }}
        asrSettings={{
          baseUrl: "https://asr.example.com/v1",
          modelName: "asr-test",
          savedApiKeyConfigured: true,
          savedApiKeyPreview: "asr-***",
          asrConfigured: true,
          asrSource: "user",
        }}
        globalSettings={{ theme: "light", updatedAt: null }}
        saveLlmSettings={saveLlmSettings}
        clearLlmApiKey={() => undefined}
        saveAsrSettings={saveAsrSettings}
        clearAsrApiKey={() => undefined}
        saveTheme={() => undefined}
      />,
    )

    fireEvent.press(screen.getByText("保存大模型"))
    fireEvent.press(screen.getByText("保存语音识别"))

    expect(saveLlmSettings).toHaveBeenCalledWith({
      baseUrl: "https://llm.example.com/v1",
      modelName: "gpt-test",
      promptAssemblyMode: "system",
    })
    expect(saveAsrSettings).toHaveBeenCalledWith({
      baseUrl: "https://asr.example.com/v1",
      modelName: "asr-test",
    })
  })
})
