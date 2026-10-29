import * as React from "react";
import { createContext, useState } from "react";
import { useContext } from "react";
import { useQuestEditor } from "../../context/QuestEditorContext";
import { useTool } from "../../context/ToolContext";

export interface LayoutContextState {
  isOpen: boolean;
  onToggle: () => void;
}

const context = createContext({} as LayoutContextState);

export const useLayout = () => {
  const layoutContext = useContext(context);
  return layoutContext;
}
export function LayoutProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(true);
  const { form, handleSaveQuest } = useQuestEditor();
  const { tool } = useTool();
  const Shell = tool === "QuestEditor" ? "form" : "div";

  return (
    <context.Provider value={{ isOpen, onToggle: () => setIsOpen(!isOpen) }}>
      <Shell
        className="w-full h-full flex flex-row dark:bg-[#282a36] dark:text-zinc-400"
        onSubmit={tool === "QuestEditor" ? form.handleSubmit((data) => {
          handleSaveQuest(data);
        }) : undefined}
      >
        {isOpen && (
          <div
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-black/20 backdrop-blur-sm dark:bg-slate-900/80 md:hidden z-10"
          />
        )}

        {children}
      </Shell>
    </context.Provider>
  );
}
