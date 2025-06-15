import asyncio


class ChatSession:
    async def invoke(self):
        async def message_stream():
            for i in range(5):
                await asyncio.sleep(1)  # simulate delay (like message arriving)
                yield f"Message {i + 1}"

        return message_stream()


chat = ChatSession()


async def main():
    async for message in await chat.invoke():
        print("Got:", message)


# ✅ Correct way to run the coroutine
asyncio.run(main())
