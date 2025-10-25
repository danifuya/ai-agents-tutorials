"use client";

import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type ChatModelAdapter,
} from "@assistant-ui/react";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";

const MyModelAdapter: ChatModelAdapter = {
  async run({ messages, abortSignal }) {
    const result = await fetch("http://localhost:8080/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      // forward the messages in the chat to the API
      body: JSON.stringify({
        messages,
      }),
      // if the user hits the "cancel" button or escape keyboard key, cancel the request
      signal: abortSignal,
    });

    const data = await result.json();
    return {
      content: [
        {
          type: "text",
          text: data.message,
        },
      ],
    };
  },
};

export function MyRuntimeProvider() {
  const runtime = useLocalRuntime(MyModelAdapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="grid h-full grid-cols-[200px_1fr]">
        <ThreadList />
        <Thread />
      </div>
    </AssistantRuntimeProvider>
  );
}
