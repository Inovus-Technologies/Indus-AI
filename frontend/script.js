// Modified: script.js
// --- STATE MANAGEMENT ---
let currentContextEntity = null;
let conversationHistory = [];
let currentConversationId = null;
let touchStartX = 0;
let touchEndX = 0;

// --- DYNAMIC API URL ---
// Using an empty string means "use the current server's address automatically"
const API_BASE_URL = ""; 

// --- UI ELEMENT SELECTORS ---
const themeToggleButton = document.querySelector(".theme-toggle");
const userInput = document.getElementById("user-input");
const sendButton = document.querySelector(".send-btn");
const chatForm = document.querySelector(".chat-input-area");
const sidebar = document.getElementById("sidebar");
const chatList = document.getElementById("chat-list");
const appContainer = document.querySelector(".app");
const backdrop = document.getElementById("backdrop");

// --- SVG ICONS ---
const sunIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
const moonIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;

// --- THEME LOGIC ---
function applyTheme(isDarkMode) {
  document.body.classList.toggle("light-mode", !isDarkMode);
  themeToggleButton.innerHTML = isDarkMode ? sunIcon : moonIcon;
}
function toggleTheme() {
  const isCurrentlyLight = document.body.classList.contains("light-mode");
  applyTheme(isCurrentlyLight);
}

// --- ON PAGE LOAD ---
document.addEventListener('DOMContentLoaded', () => {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(prefersDark);

  userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
    const hasText = userInput.value.trim() !== '';
    sendButton.classList.toggle('visible', hasText);
  });

  setTimeout(() => {
    const splash = document.getElementById("splash-screen");
    if(splash) splash.classList.add("hidden");
    document.querySelector('.app').style.display = 'flex';
    createNewChat(); 
  }, 3000);

  // Swipe detection
  document.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });
  document.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
  });

  // Drag sidebar
  let sidebarTouchStartX = 0;
  let sidebarTouchPrevX = 0;
  sidebar.addEventListener('touchstart', (e) => {
    sidebarTouchStartX = e.changedTouches[0].screenX;
    sidebarTouchPrevX = sidebarTouchStartX;
    sidebar.style.transition = 'none';
  });
  sidebar.addEventListener('touchmove', (e) => {
    const currentX = e.changedTouches[0].screenX;
    const delta = currentX - sidebarTouchPrevX;
    sidebarTouchPrevX = currentX;
    let newTranslate = parseFloat(getComputedStyle(sidebar).transform.split(',')[4]) + delta || delta;
    if (newTranslate < -sidebar.offsetWidth) newTranslate = -sidebar.offsetWidth;
    sidebar.style.transform = `translateX(${newTranslate}px)`;
  });
  sidebar.addEventListener('touchend', (e) => {
    sidebar.style.transition = 'transform 0.3s ease'; 
    const delta = e.changedTouches[0].screenX - sidebarTouchStartX;
    if (delta < -50 || parseFloat(getComputedStyle(sidebar).transform.split(',')[4]) < -sidebar.offsetWidth / 2) {
      toggleSidebar();
    } else {
      sidebar.style.transform = 'translateX(0)';
    }
  });
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => applyTheme(e.matches));

// --- SWIPE HANDLING ---
function handleSwipe() {
  const swipeThreshold = 50;
  if (touchEndX - touchStartX > swipeThreshold && touchStartX < 50) { 
    if (!sidebar.classList.contains('open')) {
      toggleSidebar();
    }
  } else if (touchStartX - touchEndX > swipeThreshold && sidebar.classList.contains('open')) {
    toggleSidebar();
  }
}

// --- SIDEBAR TOGGLE ---
function toggleSidebar() {
  sidebar.classList.toggle('open');
  appContainer.classList.toggle('sidebar-open');
  backdrop.classList.toggle('visible');
  if (sidebar.classList.contains('open')) {
    loadChatList();
    sidebar.style.transform = 'translateX(0)';
  } else {
    sidebar.style.transform = 'translateX(-100%)';
  }
}

// --- LOAD CHAT LIST ---
function loadChatList() {
  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/chats`)
    .then(res => res.json())
    .then(data => {
      chatList.innerHTML = '';
      data.chats.forEach(chat => {
        const chatItem = document.createElement("div");
        chatItem.className = "chat-item";
        chatItem.innerHTML = `
          <div class="chat-item-title" onclick="loadChat(${chat.id}, '${chat.title}')">${chat.title}</div>
          <div class="chat-item-date">${new Date(chat.created_at).toLocaleString()}</div>
          <div class="chat-item-actions">
            <button onclick="renameChat(${chat.id})">Rename</button>
            <button onclick="deleteChat(${chat.id})">Delete</button>
          </div>
        `;
        chatList.appendChild(chatItem);
      });
    })
    .catch(() => console.error("Error loading chats"));
}

// --- CREATE NEW CHAT ---
function createNewChat() {
  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/new_chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "New Chat" })
  })
    .then(res => res.json())
    .then(data => {
      currentConversationId = data.conversation_id;
      conversationHistory = [];
      document.getElementById("chat-box").innerHTML = '';
      if (sidebar.classList.contains('open')) {
        toggleSidebar(); 
      }
    })
    .catch(() => console.error("Error creating new chat"));
}

// --- LOAD EXISTING CHAT ---
function loadChat(id, title) {
  currentConversationId = id;
  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/chat/${id}`)
    .then(res => res.json())
    .then(data => {
      conversationHistory = data.history || [];
      const chatBox = document.getElementById("chat-box");
      chatBox.innerHTML = '';
      conversationHistory.forEach((msg, index) => {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${msg.role}`;
        msgDiv.innerText = msg.content;
        chatBox.appendChild(msgDiv);
        if (msg.role === 'assistant') {
          const prevUser = conversationHistory[index - 1]?.content || '';
          addFeedbackButtons(msgDiv, prevUser, msg.content);
        }
      });
      scrollToBottom();
      toggleSidebar(); 
    })
    .catch(() => console.error("Error loading chat"));
}

// --- RENAME CHAT ---
function renameChat(id) {
  const newTitle = prompt("Enter new title:");
  if (newTitle) {
    // UPDATED: Use API_BASE_URL
    fetch(`${API_BASE_URL}/rename_chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: id, new_title: newTitle })
    })
      .then(() => loadChatList())
      .catch(() => console.error("Error renaming chat"));
  }
}

// --- DELETE CHAT ---
function deleteChat(id) {
  if (confirm("Delete this chat?")) {
    // UPDATED: Use API_BASE_URL
    fetch(`${API_BASE_URL}/delete_chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: id })
    })
      .then(() => {
        loadChatList();
        if (currentConversationId === id) {
          createNewChat();
        }
      })
      .catch(() => console.error("Error deleting chat"));
  }
}

// --- CHAT LOGIC ---
chatForm.addEventListener('submit', sendMessage);
function scrollToBottom() {
  requestAnimationFrame(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  });
}

function sendMessage(e) {
  e.preventDefault();
  const chatBox = document.getElementById("chat-box");
  const message = userInput.value.trim();
  if (!message) return;
  if (!currentConversationId) {
    createNewChat(() => sendMessage(e));
    return;
  }

  const userMsg = document.createElement("div");
  userMsg.className = "message user";
  userMsg.innerText = message;
  chatBox.appendChild(userMsg);
  userInput.value = "";
  userInput.dispatchEvent(new Event('input')); 
  scrollToBottom();

  const typingIndicator = document.createElement("div");
  typingIndicator.className = "message ai typing-indicator";
  typingIndicator.innerHTML = `<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>`;
  chatBox.appendChild(typingIndicator);
  scrollToBottom();

  const isFirstMessage = conversationHistory.length === 0;

  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        user_input: message,
        history: conversationHistory,
        context_entity: currentContextEntity,
        conversation_id: currentConversationId
    })
  })
    .then(res => res.json())
    .then(data => {
      typingIndicator.remove();
      conversationHistory = data.history || [];
      currentContextEntity = data.context_entity || null;
 
      const aiMsg = document.createElement("div");
      aiMsg.className = "message ai";
      chatBox.appendChild(aiMsg);
      animateText(aiMsg, data.response || "No response.", () => {
        addFeedbackButtons(aiMsg, message, data.response || "No response.");
        scrollToBottom();
        if (isFirstMessage) {
          const newTitle = message.slice(0, 30) + (message.length > 30 ? '...' : '');
          // UPDATED: Use API_BASE_URL for auto-rename
          fetch(`${API_BASE_URL}/rename_chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ conversation_id: currentConversationId, new_title: newTitle })
          })
            .then(() => {
              if (sidebar.classList.contains('open')) {
                loadChatList();
              }
            })
            .catch(() => console.error("Error auto-renaming chat"));
        }
      });
    })
    .catch(() => {
      typingIndicator.remove();
      const errMsg = document.createElement("div");
      errMsg.className = "message ai";
      errMsg.innerText = "Error reaching server.";
      chatBox.appendChild(errMsg);
      scrollToBottom();
    });
}

function animateText(element, text, callback) {  
  let index = 0;
  const cursor = document.createElement('span');
  cursor.className = 'typing-cursor';
  cursor.textContent = '|';
  element.appendChild(cursor);

  function typeNextChar() {
    if (index < text.length) {
      const charSpan = document.createElement('span');
      charSpan.className = 'animated-char';
      charSpan.textContent = text.charAt(index);
      element.insertBefore(charSpan, cursor);
      index++;
      const delay = Math.floor(Math.random() * 50) + 30;
      setTimeout(typeNextChar, delay);
      if (index % 5 === 0) scrollToBottom();
    } else {  
      element.removeChild(cursor);
      if (callback) callback();  
      scrollToBottom();
    }  
  }
  typeNextChar();
}

function addFeedbackButtons(container, question, ai_response) {  
  const wrapper = document.createElement("div");
  wrapper.className = "feedback-wrapper";  
  const feedbackDiv = document.createElement("div");
  feedbackDiv.className = "feedback-buttons";

  // Regenerate
  const regenerateBtn = document.createElement("button");  
  regenerateBtn.className = "feedback-btn regenerate";  
  regenerateBtn.title = "Regenerate Response";
  regenerateBtn.innerHTML = `<svg class="thumb-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 3 21 8 16 8" /><polyline points="3 21 3 16 8 16" /><path d="M3.5 9a8.5 8.5 0 0 1 13-3.5" /><path d="M20.5 15a8.5 8.5 0 0 1-13 3.5" /></svg>`;
  regenerateBtn.onclick = () => {
    if (conversationHistory.length > 0) {
      const lastUserMessage = conversationHistory[conversationHistory.length - 2].content;
      sendRegenerate(lastUserMessage);
    }
  };

  // Copy
  const copyBtn = document.createElement("button");  
  copyBtn.className = "feedback-btn copy";  
  copyBtn.title = "Copy Response";
  copyBtn.innerHTML = `<svg class="thumb-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h1a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1" /><rect x="9" y="2" width="6" height="4" rx="1" ry="1" /></svg>`;
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(ai_response); 
    copyBtn.classList.add("active");
  };  

  // Like
  const likeBtn = document.createElement("button");  
  likeBtn.className = "feedback-btn like";
  likeBtn.title = "Helpful";
  likeBtn.innerHTML = `<svg class="thumb-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"/><path d="M15 5.88L14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a2 2 0 0 1 3 1.88v2Z"/></svg>`;
  likeBtn.onclick = () => {
    sendFeedback(question, ai_response, "like", likeBtn);
    dislikeBtn.style.display = 'none';
    likeBtn.classList.add("active");
  };

  // Dislike
  const dislikeBtn = document.createElement("button");  
  dislikeBtn.className = "feedback-btn dislike";  
  dislikeBtn.title = "Not Helpful";
  dislikeBtn.innerHTML = `<svg class="thumb-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"/><path d="M9 18.12L10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a2 2 0 0 1-3-1.88v-2Z"/></svg>`;
  dislikeBtn.onclick = () => {
    sendFeedback(question, ai_response, "dislike", dislikeBtn);
    likeBtn.style.display = 'none';
    dislikeBtn.classList.add("active");
  };

  feedbackDiv.appendChild(regenerateBtn);
  feedbackDiv.appendChild(copyBtn);
  feedbackDiv.appendChild(likeBtn);  
  feedbackDiv.appendChild(dislikeBtn);  
  wrapper.appendChild(feedbackDiv);  
  container.appendChild(wrapper);
}

function sendRegenerate(lastMessage) {
  const chatBox = document.getElementById("chat-box");
  const typingIndicator = document.createElement("div");
  typingIndicator.className = "message ai typing-indicator";
  typingIndicator.innerHTML = `<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>`;
  chatBox.appendChild(typingIndicator);
  scrollToBottom();

  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
        user_input: lastMessage,
        history: conversationHistory,
        context_entity: currentContextEntity,
        conversation_id: currentConversationId
    })
  })
    .then(res => res.json())
    .then(data => {
      typingIndicator.remove();
      conversationHistory = data.history || [];
      currentContextEntity = data.context_entity || null;
 
      const aiMsg = document.createElement("div");
      aiMsg.className = "message ai";
      chatBox.appendChild(aiMsg);
      animateText(aiMsg, data.response || "No response.", () => {
        addFeedbackButtons(aiMsg, lastMessage, data.response || "No response.");
        scrollToBottom();
      });
    })
    .catch(() => {
      typingIndicator.remove();
      const errMsg = document.createElement("div");
      errMsg.className = "message ai";
      errMsg.innerText = "Error regenerating response.";
      chatBox.appendChild(errMsg);
      scrollToBottom();
    });
}

function sendFeedback(question, ai_response, feedbackType, button) {
  if (feedbackType === "like") {
    button.classList.add("active");
  } else {
    button.classList.add("shake");
    button.classList.add("active");
  }

  // UPDATED: Use API_BASE_URL
  fetch(`${API_BASE_URL}/feedback`, {  
    method: "POST",  
    headers: { "Content-Type": "application/json" },  
    body: JSON.stringify({ 
      question: question, 
      ai_response: ai_response, 
      feedback: feedbackType 
    })  
  });
}
