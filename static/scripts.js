document.addEventListener("DOMContentLoaded", () => {
  const chatBody = document.querySelector(".chat-body");
  const messageInput = document.querySelector(".message-input");
  const sendMessageButton = document.querySelector("#send-message");
  const fileInput = document.querySelector("#file-input");
  const chatbotToggler = document.querySelector("#chatbot-toggler");
  const closeChatbot = document.querySelector("#close-chatbot");
  const fileUpload = document.querySelector("#file-upload");

  if (!messageInput) return;

  const initialInputHeight = messageInput.scrollHeight;

  const createMessageElement = (content, ...classes) => {
    const div = document.createElement("div");
    div.classList.add("message", ...classes);
    div.innerHTML = content;
    return div;
  };

  const handleOutgoingMessage = () => {
    const userText = messageInput.value.trim();
    if (!userText) return;

    const form = document.querySelector("form.chat-form");
    if (form) form.submit();
  };

  messageInput.addEventListener("keydown", (e) => {
    const userMessage = e.target.value.trim();
    if (e.key === "Enter" && userMessage && !e.shiftKey && window.innerWidth > 768) {
      e.preventDefault();
      handleOutgoingMessage();
    }
  });

  messageInput.addEventListener("input", () => {
    messageInput.style.height = `${initialInputHeight}px`;
    messageInput.style.height = `${messageInput.scrollHeight}px`;
  });

  if (chatbotToggler) {
    chatbotToggler.addEventListener("click", () => {
      document.body.classList.toggle("show-chatbot");
    });
  }

  if (closeChatbot) {
    closeChatbot.addEventListener("click", () => {
      document.body.classList.remove("show-chatbot");
    });
  }

  if (sendMessageButton) {
    sendMessageButton.addEventListener("click", (e) => {
      e.preventDefault();
      handleOutgoingMessage();
    });
  }

  if (fileUpload && fileInput) {
    fileUpload.addEventListener("click", () => fileInput.click());
  }

  const picker = new EmojiMart.Picker({
    theme: "light",
    skinTonePosition: "none",
    preview: "none",
    onEmojiSelect: (emoji) => {
      const { selectionStart: start, selectionEnd: end } = messageInput;
      messageInput.setRangeText(emoji.native, start, end, "end");
      messageInput.focus();
    },
    onClickOutside: (e) => {
      if (e.target.id === "emoji-picker") {
        document.body.classList.toggle("show-emoji-picker");
      } else {
        document.body.classList.remove("show-emoji-picker");
      }
    }
  });

  document.querySelector(".chat-form")?.appendChild(picker);
});
