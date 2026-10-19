/**
 * Administrator moderation panel.
 *
 * The server enforces the administrator role on every endpoint. The panel is
 * only shown for administrators as a usability measure, never as a security
 * boundary.
 */

const PAGE_SIZE = 20;

function formatDateTime(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function truncate(text, limit = 180) {
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit).trimEnd()}…`;
}

function errorText(error, fallback) {
  if (error.code === "CSRF_FAILED") {
    return "Your security token was refreshed. Please try the action again.";
  }
  return error.message || fallback;
}

export function createModeration({ api, state, notify, handleError, onFeedChanged }) {
  const panel = document.getElementById("moderation-panel");
  const list = document.getElementById("moderation-list");
  const empty = document.getElementById("moderation-empty");
  const status = document.getElementById("moderation-status");
  const loadMoreButton = document.getElementById("moderation-load-more");
  const filter = document.getElementById("visibility-filter");
  const template = document.getElementById("moderation-card-template");

  const dialog = document.getElementById("delete-dialog");
  const dialogExcerpt = document.getElementById("delete-excerpt");
  const dialogError = document.getElementById("delete-error");
  const dialogCancel = document.getElementById("delete-cancel");
  const dialogConfirm = document.getElementById("delete-confirm");

  let pendingDeleteId = null;
  let lastTrigger = null;

  function itemById(id) {
    return state.moderation.items.find((item) => item.id === id) || null;
  }

  function setStatus(message) {
    status.textContent = message;
  }

  function setBusy(busy) {
    state.moderation.loading = busy;
    panel.setAttribute("aria-busy", busy ? "true" : "false");
    filter.disabled = busy;
    loadMoreButton.disabled = busy;
  }

  function render() {
    list.replaceChildren();

    for (const item of state.moderation.items) {
      const fragment = template.content.cloneNode(true);
      const card = fragment.querySelector(".moderation-card");
      card.dataset.id = String(item.id);
      card.classList.toggle("is-hidden", !item.isVisible);

      fragment.querySelector(".moderation-card__giver").textContent =
        item.giver.name;
      fragment.querySelector(".moderation-card__recipient").textContent =
        item.recipient.name;
      fragment.querySelector(".moderation-card__message").textContent =
        item.message;

      const time = fragment.querySelector(".moderation-card__time");
      time.dateTime = item.createdAt;
      time.textContent = formatDateTime(item.createdAt);

      const visibility = fragment.querySelector(
        ".moderation-card__visibility",
      );
      visibility.textContent = item.isVisible ? "Visible" : "Hidden";
      visibility.classList.add(
        item.isVisible ? "badge--visible" : "badge--hidden",
      );

      const hideButton = fragment.querySelector(".hide-kudos");
      const restoreButton = fragment.querySelector(".restore-kudos");
      const deleteButton = fragment.querySelector(".delete-kudos");
      hideButton.dataset.id = String(item.id);
      restoreButton.dataset.id = String(item.id);
      deleteButton.dataset.id = String(item.id);
      hideButton.hidden = !item.isVisible;
      restoreButton.hidden = item.isVisible;

      list.appendChild(fragment);
    }

    empty.hidden = state.moderation.loading || state.moderation.items.length > 0;
    loadMoreButton.hidden = !state.moderation.hasMore;
  }

  async function load({ reset = false } = {}) {
    if (state.moderation.loading) {
      return;
    }

    if (reset) {
      state.moderation.items = [];
      state.moderation.nextOffset = null;
      state.moderation.hasMore = false;
      render();
    } else if (!state.moderation.hasMore) {
      return;
    }

    setBusy(true);
    setStatus("Loading moderation list…");

    try {
      const data = await api.adminKudos({
        limit: PAGE_SIZE,
        offset: reset ? 0 : state.moderation.nextOffset,
        visibility: state.moderation.visibility,
      });

      if (reset) {
        state.moderation.items = data.items;
      } else {
        const seen = new Set(state.moderation.items.map((item) => item.id));
        for (const item of data.items) {
          if (!seen.has(item.id)) {
            state.moderation.items.push(item);
            seen.add(item.id);
          }
        }
      }

      state.moderation.nextOffset = data.pagination.nextOffset;
      state.moderation.hasMore = data.pagination.hasMore;
      render();

      if (state.moderation.items.length === 0) {
        setStatus("The moderation list is empty.");
      } else {
        setStatus(
          `${state.moderation.items.length} kudos loaded.`,
        );
      }
    } catch (error) {
      const handled = await handleError(error, { context: "moderation" });
      if (!(handled && error.status === 401)) {
        setStatus(
          errorText(error, "Could not load the moderation list."),
        );
      }
    } finally {
      setBusy(false);
      render();
    }
  }

  async function moderate(id, action, button) {
    const item = itemById(id);
    if (!item) {
      return;
    }

    button.disabled = true;
    setStatus(action === "hide" ? "Hiding kudos…" : "Restoring kudos…");

    try {
      if (action === "hide") {
        await api.hideKudos(id);
        notify("Kudos hidden. It is no longer in the employee feed.", "success");
      } else {
        await api.restoreKudos(id);
        notify("Kudos restored. It is visible in the employee feed again.", "success");
      }
      await load({ reset: true });
      await onFeedChanged();
    } catch (error) {
      const handled = await handleError(error, { context: "moderation" });
      if (!(handled && error.status === 401)) {
        setStatus(errorText(error, "The moderation action failed."));
        if (error.code === "KUDOS_NOT_FOUND") {
          await load({ reset: true });
          await onFeedChanged();
        }
      }
    } finally {
      button.disabled = false;
    }
  }

  function openDeleteDialog(item, trigger) {
    pendingDeleteId = item.id;
    lastTrigger = trigger;
    dialogExcerpt.textContent = truncate(item.message);
    dialogError.textContent = "";
    dialogError.hidden = true;
    dialogConfirm.disabled = false;
    dialogCancel.disabled = false;
    dialogConfirm.textContent = "Delete permanently";
    dialog.showModal();
    dialogCancel.focus();
  }

  function closeDeleteDialog() {
    if (dialog.open) {
      dialog.close();
    }
    pendingDeleteId = null;
    if (lastTrigger && typeof lastTrigger.focus === "function") {
      lastTrigger.focus();
    }
    lastTrigger = null;
  }

  function showDeleteError(message) {
    dialogError.textContent = message;
    dialogError.hidden = false;
    dialogConfirm.disabled = false;
    dialogCancel.disabled = false;
    dialogConfirm.textContent = "Delete permanently";
  }

  async function confirmDelete() {
    if (!pendingDeleteId) {
      return;
    }

    const id = pendingDeleteId;
    dialogConfirm.disabled = true;
    dialogCancel.disabled = true;
    dialogConfirm.textContent = "Deleting…";
    dialogError.hidden = true;

    try {
      await api.deleteKudos(id);
      closeDeleteDialog();
      notify("Kudos deleted permanently.", "success");
      await load({ reset: true });
      await onFeedChanged();
    } catch (error) {
      if (error.code === "KUDOS_NOT_FOUND") {
        closeDeleteDialog();
        notify("That kudos was already deleted.", "error");
        await load({ reset: true });
        await onFeedChanged();
        return;
      }
      // A session expiry moves the whole UI back to the identity picker, so
      // the dialog must close. Every other failure (including a refreshed
      // CSRF token, lost permission, or a network error) keeps the dialog
      // open so the administrator can retry or cancel.
      if (error.status === 401) {
        closeDeleteDialog();
        await handleError(error, { context: "moderation" });
        return;
      }

      await handleError(error, { context: "moderation" });
      showDeleteError(
        errorText(error, "Could not delete this kudos. Please try again."),
      );
    }
  }

  list.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) {
      return;
    }
    const id = Number(button.dataset.id);
    if (!Number.isInteger(id)) {
      return;
    }

    if (button.classList.contains("hide-kudos")) {
      moderate(id, "hide", button);
    } else if (button.classList.contains("restore-kudos")) {
      moderate(id, "restore", button);
    } else if (button.classList.contains("delete-kudos")) {
      const item = itemById(id);
      if (item) {
        openDeleteDialog(item, button);
      }
    }
  });

  filter.addEventListener("change", () => {
    state.moderation.visibility = filter.value;
    load({ reset: true });
  });

  loadMoreButton.addEventListener("click", () => {
    load({ reset: false });
  });

  dialogCancel.addEventListener("click", closeDeleteDialog);
  dialogConfirm.addEventListener("click", confirmDelete);
  dialog.addEventListener("close", () => {
    if (pendingDeleteId !== null) {
      pendingDeleteId = null;
      if (lastTrigger && typeof lastTrigger.focus === "function") {
        lastTrigger.focus();
      }
      lastTrigger = null;
    }
  });

  function setVisible(visible) {
    panel.hidden = !visible;
    if (visible) {
      filter.value = state.moderation.visibility;
      load({ reset: true });
    } else {
      state.moderation.items = [];
      state.moderation.hasMore = false;
      state.moderation.nextOffset = null;
      list.replaceChildren();
      empty.hidden = true;
      setStatus("");
    }
  }

  return {
    setVisible,
    load,
    reset() {
      setVisible(false);
      state.moderation.visibility = "all";
      filter.value = "all";
    },
  };
}
