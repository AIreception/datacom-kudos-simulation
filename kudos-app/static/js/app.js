/**
 * Kudos demo frontend.
 *
 * Startup: obtain a CSRF token, check for an existing demo session, then show
 * either the identity picker or the dashboard. All user-generated text is
 * inserted with textContent; no user content is ever parsed as HTML.
 */

import { api, ApiError, setCsrfToken } from "./api.js";
import { createModeration } from "./moderation.js";

const PAGE_SIZE = 20;

const state = {
  csrfToken: null,
  me: null,
  isAdmin: false,
  users: [],
  kudos: [],
  nextOffset: null,
  hasMore: false,
  loadingFeed: false,
  feedError: null,
  submitting: false,
  signingIn: false,
  sessionTransition: false,
  moderation: {
    items: [],
    nextOffset: null,
    hasMore: false,
    visibility: "all",
    loading: false,
  },
};

const els = {
  picker: document.getElementById("identity-picker"),
  pickerStatus: document.getElementById("picker-status"),
  identityList: document.getElementById("identity-list"),
  appContent: document.getElementById("app-content"),
  userMenu: document.getElementById("user-menu"),
  currentUserName: document.getElementById("current-user-name"),
  currentUserRole: document.getElementById("current-user-role"),
  switchUser: document.getElementById("switch-user"),
  form: document.getElementById("kudos-form"),
  recipient: document.getElementById("recipient"),
  recipientError: document.getElementById("recipient-error"),
  message: document.getElementById("message"),
  messageError: document.getElementById("message-error"),
  charCount: document.getElementById("char-count"),
  formError: document.getElementById("form-error"),
  formStatus: document.getElementById("form-status"),
  submitKudos: document.getElementById("submit-kudos"),
  feedList: document.getElementById("feed-list"),
  feedStatus: document.getElementById("feed-status"),
  feedEmpty: document.getElementById("feed-empty"),
  loadMore: document.getElementById("load-more"),
  feedRetry: document.getElementById("feed-retry"),
  feedTemplate: document.getElementById("kudos-card-template"),
};

function notify(message, type = "info") {
  const region = document.getElementById("toast-region");
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  region.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, 4500);
}

function initials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 1).toUpperCase();
  }
  return `${parts[0].slice(0, 1)}${parts[parts.length - 1].slice(0, 1)}`.toUpperCase();
}

function formatAbsolute(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatRelative(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const absoluteSeconds = Math.abs(diffSeconds);
  const formatter = new Intl.RelativeTimeFormat(undefined, {
    numeric: "auto",
  });

  if (absoluteSeconds < 45) {
    return formatter.format(0, "second");
  }
  if (absoluteSeconds < 60 * 60) {
    return formatter.format(Math.round(diffSeconds / 60), "minute");
  }
  if (absoluteSeconds < 60 * 60 * 24) {
    return formatter.format(Math.round(diffSeconds / 3600), "hour");
  }
  if (absoluteSeconds < 60 * 60 * 24 * 7) {
    return formatter.format(Math.round(diffSeconds / 86400), "day");
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function setCurrentUser(user) {
  state.me = user;
  state.isAdmin = Boolean(user && user.role === "admin");
  els.userMenu.hidden = !user;
  if (user) {
    els.currentUserName.textContent = user.name;
    els.currentUserRole.hidden = !state.isAdmin;
  } else {
    els.currentUserName.textContent = "";
    els.currentUserRole.hidden = true;
  }
}

function clearFormErrors() {
  for (const [element, input] of [
    [els.recipientError, els.recipient],
    [els.messageError, els.message],
    [els.formError, null],
  ]) {
    element.textContent = "";
    element.hidden = true;
    if (input) {
      input.removeAttribute("aria-invalid");
    }
  }
}

function showFieldError(element, input, message) {
  element.textContent = message;
  element.hidden = false;
  if (input) {
    input.setAttribute("aria-invalid", "true");
  }
}

function updateCounter() {
  const count = Array.from(els.message.value).length;
  els.charCount.textContent = `${count} / 500`;
  els.charCount.classList.toggle("is-over", count > 500);
}

function updateFeedState() {
  els.feedEmpty.hidden =
    state.loadingFeed ||
    state.kudos.length > 0 ||
    Boolean(state.feedError);
  els.loadMore.hidden =
    !state.hasMore || state.loadingFeed || Boolean(state.feedError);
  els.loadMore.disabled = state.loadingFeed;
  els.feedRetry.hidden = !state.feedError || state.loadingFeed;
}

function renderFeedItem(item) {
  const fragment = els.feedTemplate.content.cloneNode(true);
  fragment.querySelector(".kudos-card__giver").textContent = item.giver.name;
  fragment.querySelector(".kudos-card__recipient").textContent =
    item.recipient.name;
  fragment.querySelector(".kudos-card__avatar").textContent = initials(
    item.giver.name,
  );
  fragment.querySelector(".kudos-card__message").textContent = item.message;

  const time = fragment.querySelector(".kudos-card__time");
  time.dateTime = item.createdAt;
  time.textContent = formatRelative(item.createdAt);
  time.title = formatAbsolute(item.createdAt);

  els.feedList.appendChild(fragment);
}

function renderFeed() {
  els.feedList.replaceChildren();
  for (const item of state.kudos) {
    renderFeedItem(item);
  }
  updateFeedState();
}

async function loadFeed({ reset = false } = {}) {
  if (state.loadingFeed) {
    return;
  }
  if (!reset && !state.hasMore) {
    return;
  }

  if (reset) {
    state.kudos = [];
    state.nextOffset = null;
    state.hasMore = false;
    state.feedError = null;
    renderFeed();
  }

  state.loadingFeed = true;
  state.feedError = null;
  els.feedStatus.textContent = "Loading kudos…";
  updateFeedState();

  try {
    const data = await api.kudos({
      limit: PAGE_SIZE,
      offset: reset ? 0 : state.nextOffset,
    });

    if (reset) {
      state.kudos = data.items;
    } else {
      const seen = new Set(state.kudos.map((item) => item.id));
      for (const item of data.items) {
        if (!seen.has(item.id)) {
          state.kudos.push(item);
          seen.add(item.id);
        }
      }
    }

    state.nextOffset = data.pagination.nextOffset;
    state.hasMore = data.pagination.hasMore;
    els.feedStatus.textContent =
      state.kudos.length > 0 ? `${state.kudos.length} kudos shown.` : "";
  } catch (error) {
    if (await handleApiError(error, { context: "feed" })) {
      els.feedStatus.textContent = "";
    } else {
      state.feedError = error.message || "Could not load kudos.";
      els.feedStatus.textContent = state.feedError;
    }
  } finally {
    state.loadingFeed = false;
    renderFeed();
  }
}

async function loadColleagues() {
  try {
    const data = await api.users();
    state.users = data.users;

    els.recipient.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a colleague";
    placeholder.disabled = true;
    placeholder.selected = true;
    els.recipient.appendChild(placeholder);

    const colleagues = state.users.filter(
      (user) => !state.me || user.id !== state.me.id,
    );

    for (const user of colleagues) {
      const option = document.createElement("option");
      option.value = String(user.id);
      option.textContent = user.department
        ? `${user.name} — ${user.department}`
        : user.name;
      els.recipient.appendChild(option);
    }

    if (colleagues.length === 0) {
      els.recipient.disabled = true;
      els.submitKudos.disabled = true;
      els.formStatus.textContent =
        "There are no other active colleagues to recognise.";
    } else {
      els.recipient.disabled = false;
      els.submitKudos.disabled = false;
      els.formStatus.textContent = "";
    }
  } catch (error) {
    if (!(await handleApiError(error, { context: "form" }))) {
      els.formStatus.textContent =
        error.message || "Could not load the colleague list.";
    }
  }
}

async function submitKudos(event) {
  event.preventDefault();
  if (state.submitting) {
    return;
  }

  clearFormErrors();
  els.formStatus.textContent = "";

  const recipientId = Number.parseInt(els.recipient.value, 10);
  if (!Number.isInteger(recipientId) || recipientId <= 0) {
    showFieldError(
      els.recipientError,
      els.recipient,
      "Choose a colleague to recognise.",
    );
    els.recipient.focus();
    return;
  }

  const rawMessage = els.message.value;
  const trimmedMessage = rawMessage.trim();
  if (!trimmedMessage) {
    showFieldError(els.messageError, els.message, "Message cannot be empty.");
    els.message.focus();
    return;
  }
  if (Array.from(trimmedMessage).length > 500) {
    showFieldError(
      els.messageError,
      els.message,
      "Message must be 500 characters or fewer.",
    );
    els.message.focus();
    return;
  }

  state.submitting = true;
  els.submitKudos.disabled = true;
  els.submitKudos.textContent = "Sending…";
  els.form.setAttribute("aria-busy", "true");
  els.formStatus.textContent = "Sending kudos…";

  try {
    await api.createKudos({
      recipientId,
      message: rawMessage,
    });

    els.message.value = "";
    els.recipient.value = "";
    updateCounter();
    els.formStatus.textContent = "Kudos sent.";
    notify("Kudos sent.", "success");

    await loadFeed({ reset: true });
    if (state.isAdmin) {
      moderation.load({ reset: true });
    }
  } catch (error) {
    if (await handleApiError(error, { context: "form" })) {
      els.formStatus.textContent = "Please try again.";
    } else if (error instanceof ApiError && Object.keys(error.fields).length) {
      if (error.fields.recipientId) {
        showFieldError(
          els.recipientError,
          els.recipient,
          error.fields.recipientId,
        );
      }
      if (error.fields.message) {
        showFieldError(els.messageError, els.message, error.fields.message);
      }
      if (!error.fields.recipientId && !error.fields.message) {
        showFieldError(els.formError, null, error.message);
      }
      if (error.fields.recipientId) {
        els.recipient.focus();
      } else if (error.fields.message) {
        els.message.focus();
      }
    } else if (error.code === "SELF_KUDOS") {
      showFieldError(
        els.recipientError,
        els.recipient,
        "You cannot give kudos to yourself.",
      );
      els.recipient.focus();
    } else if (error.code === "RECIPIENT_NOT_FOUND") {
      showFieldError(
        els.recipientError,
        els.recipient,
        "That colleague is no longer available.",
      );
      els.recipient.focus();
    } else {
      showFieldError(
        els.formError,
        null,
        error.message || "Could not send kudos. Please try again.",
      );
    }
  } finally {
    state.submitting = false;
    els.submitKudos.disabled = false;
    els.submitKudos.textContent = "Send kudos";
    els.form.setAttribute("aria-busy", "false");
  }
}

function renderDemoUsers(users) {
  els.identityList.replaceChildren();

  for (const user of users) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "identity-button";
    button.dataset.userId = String(user.id);

    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = initials(user.name);

    const text = document.createElement("span");
    text.className = "identity-button__text";
    const name = document.createElement("span");
    name.className = "identity-button__name";
    name.textContent = user.name;
    const department = document.createElement("span");
    department.className = "identity-button__department";
    department.textContent = user.department || "Team member";
    text.append(name, department);

    button.append(avatar, text);

    if (user.role === "admin") {
      const badge = document.createElement("span");
      badge.className = "badge badge--admin";
      badge.textContent = "Administrator";
      button.appendChild(badge);
    }

    button.addEventListener("click", () => signIn(user.id));
    item.appendChild(button);
    els.identityList.appendChild(item);
  }
}

async function loadDemoUsers(message = "") {
  els.pickerStatus.textContent = "Loading demo users…";
  els.identityList.replaceChildren();

  try {
    const data = await api.getDemoUsers();
    renderDemoUsers(data.users);
    els.pickerStatus.textContent = message;
  } catch (error) {
    if (error.code === "NOT_FOUND") {
      els.pickerStatus.textContent =
        "Demo identity is disabled on this server. This environment is not usable for the demo.";
    } else {
      els.pickerStatus.textContent =
        error.message || "Could not load demo users. Please reload the page.";
    }
    notify("Could not load demo users.", "error");
  }
}

async function signIn(userId) {
  if (state.signingIn) {
    return;
  }
  state.signingIn = true;
  const buttons = els.identityList.querySelectorAll("button");
  buttons.forEach((button) => {
    button.disabled = true;
  });
  els.pickerStatus.textContent = "Signing in…";

  try {
    const data = await api.login(userId);
    setCsrfToken(data.csrfToken);
    state.csrfToken = data.csrfToken;
    setCurrentUser(data.user);
    els.picker.hidden = true;
    await enterApp();
    notify(`Signed in as ${data.user.name}.`, "success");
  } catch (error) {
    if (await handleApiError(error, { context: "identity" })) {
      els.pickerStatus.textContent = "Please try again.";
    } else {
      els.pickerStatus.textContent =
        error.message || "Could not sign in. Please try again.";
      notify("Could not sign in.", "error");
    }
  } finally {
    state.signingIn = false;
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}

async function enterApp() {
  els.picker.hidden = true;
  els.appContent.hidden = false;
  els.userMenu.hidden = false;

  state.kudos = [];
  state.nextOffset = null;
  state.hasMore = false;
  state.feedError = null;
  renderFeed();

  moderation.reset();
  await Promise.all([
    loadColleagues(),
    loadFeed({ reset: true }),
  ]);

  if (state.isAdmin) {
    moderation.setVisible(true);
  }
}

function resetComposer() {
  els.form.reset();
  els.recipient.replaceChildren();
  els.message.value = "";
  updateCounter();
  clearFormErrors();
  els.formStatus.textContent = "";
  els.submitKudos.disabled = false;
  els.submitKudos.textContent = "Send kudos";
}

async function showPicker(message = "") {
  els.appContent.hidden = true;
  els.picker.hidden = false;
  els.userMenu.hidden = true;
  setCurrentUser(null);

  state.kudos = [];
  state.nextOffset = null;
  state.hasMore = false;
  state.feedError = null;
  renderFeed();
  resetComposer();
  moderation.reset();

  await loadDemoUsers(message);
}

async function refreshCsrfToken() {
  try {
    const data = await api.getCsrf();
    setCsrfToken(data.csrfToken);
    state.csrfToken = data.csrfToken;
    return true;
  } catch (error) {
    notify(
      error.message || "Could not initialize the security token.",
      "error",
    );
    return false;
  }
}

async function enterSignedOut(message) {
  if (state.sessionTransition) {
    return;
  }
  state.sessionTransition = true;
  try {
    setCurrentUser(null);
    setCsrfToken(null);
    await refreshCsrfToken();
    await showPicker(message);
  } finally {
    state.sessionTransition = false;
  }
}

async function handleApiError(error, { context = "" } = {}) {
  if (!(error instanceof ApiError)) {
    return false;
  }

  if (error.code === "CSRF_FAILED") {
    await refreshCsrfToken();
    notify(
      "Your security token was refreshed. Please try the action again.",
      "error",
    );
    return true;
  }

  if (error.status === 401) {
    if (state.me) {
      await enterSignedOut(
        "Your demo session ended. Choose a user to continue.",
      );
    }
    return true;
  }

  if (error.code === "FORBIDDEN") {
    notify("Administrator permission is required.", "error");
    return true;
  }

  if (error.status === 413) {
    notify("The message is too large to send.", "error");
    return true;
  }

  return false;
}

async function switchUser() {
  els.switchUser.disabled = true;
  try {
    try {
      await api.logout();
    } catch (error) {
      if (error instanceof ApiError && error.code === "CSRF_FAILED") {
        await refreshCsrfToken();
        try {
          await api.logout();
        } catch (secondError) {
          // The local UI still returns to the picker below.
        }
      }
    }

    setCsrfToken(null);
    await refreshCsrfToken();
    await showPicker("You switched users. Choose a demo user to continue.");
  } finally {
    els.switchUser.disabled = false;
  }
}

const moderation = createModeration({
  api,
  state,
  notify,
  handleError: handleApiError,
  onFeedChanged: () => loadFeed({ reset: true }),
});

els.form.addEventListener("submit", submitKudos);
els.message.addEventListener("input", updateCounter);
els.recipient.addEventListener("change", () => {
  els.recipientError.textContent = "";
  els.recipientError.hidden = true;
  els.recipient.removeAttribute("aria-invalid");
});
els.loadMore.addEventListener("click", () => {
  loadFeed({ reset: false });
});
els.feedRetry.addEventListener("click", () => {
  loadFeed({ reset: true });
});
els.switchUser.addEventListener("click", switchUser);

async function bootstrap() {
  updateCounter();

  if (!("fetch" in window)) {
    els.picker.hidden = false;
    els.pickerStatus.textContent =
      "This browser does not support fetch(). Please use a modern browser.";
    return;
  }

  const hasToken = await refreshCsrfToken();
  if (!hasToken) {
    await showPicker(
      "Could not initialize the security token. Reload the page and try again.",
    );
    return;
  }

  try {
    const data = await api.me();
    setCurrentUser(data.user);
    await enterApp();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      await showPicker("Choose a demo user to begin.");
    } else {
      await showPicker(
        error.message || "Could not start the demo. Please reload the page.",
      );
      notify("Could not start the demo.", "error");
    }
  }
}

bootstrap();
