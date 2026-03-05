document.addEventListener('DOMContentLoaded', () => {
    if (!initStrictTabSessionGuard()) {
        return;
    }

    initThemeMode();
    initSidebarMenu();
    initViewButtons();
    initFriendsPageEditMode();
    initHomeCardEditMode();
    initChatAutoScroll();
    initAiHelperChat();

    const pageEdit = initPageAdminEditMode();
    const adminCenter = initAdminCenterTables();

    if (pageEdit && adminCenter) {
        pageEdit.onBeforeDisable(() => adminCenter.saveDirtyRows());
    }
});

function initThemeMode() {
    const body = document.body;
    const quickToggles = [...document.querySelectorAll('[data-theme-quick-toggle]')];
    const settingsSelect = document.getElementById('theme_mode');
    if (!body || (quickToggles.length === 0 && !settingsSelect)) {
        return null;
    }

    const normalizeTheme = (value) => (value === 'dark' ? 'dark' : 'light');
    let currentTheme = normalizeTheme(body.classList.contains('theme-dark') ? 'dark' : 'light');
    const themeTabKey = 'atlasboard_theme_tab_active';
    const isAuthPage = body.classList.contains('page-auth');
    const hasThemeTabMarker = window.sessionStorage.getItem(themeTabKey) === '1';
    if (isAuthPage && !hasThemeTabMarker) {
        currentTheme = 'light';
    }
    window.sessionStorage.setItem(themeTabKey, '1');

    const writeThemeCookie = (themeMode) => {
        document.cookie = `ui_theme_mode=${normalizeTheme(themeMode)}; Path=/; SameSite=Lax`;
    };

    const applyTheme = (themeMode) => {
        currentTheme = normalizeTheme(themeMode);
        body.classList.remove('theme-light', 'theme-dark');
        body.classList.add(`theme-${currentTheme}`);
        writeThemeCookie(currentTheme);

        quickToggles.forEach((button) => {
            const isDark = currentTheme === 'dark';
            button.textContent = `Dark Mode: ${isDark ? 'On' : 'Off'}`;
            button.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            button.dataset.themeMode = currentTheme;
        });

        if (settingsSelect && settingsSelect.value !== currentTheme) {
            settingsSelect.value = currentTheme;
        }
    };

    const persistTheme = async (themeMode) => {
        const themeUrl = body.dataset.themeSetUrl;
        if (!themeUrl) {
            return true;
        }
        try {
            const payload = new URLSearchParams();
            payload.set('theme_mode', themeMode);
            const response = await fetch(themeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: payload.toString(),
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    };

    quickToggles.forEach((button) => {
        button.addEventListener('click', async () => {
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
            await persistTheme(nextTheme);
        });
    });

    if (settingsSelect) {
        settingsSelect.addEventListener('change', () => {
            applyTheme(settingsSelect.value);
        });
    }

    applyTheme(currentTheme);
    return {
        getTheme: () => currentTheme,
    };
}

function initStrictTabSessionGuard() {
    const body = document.body;
    if (body.dataset.authenticated !== '1') {
        return true;
    }

    const sessionKey = 'atlasboard_tab_session';
    const hasTabSession = window.sessionStorage.getItem(sessionKey) === '1';
    const sessionSeed = body.dataset.sessionSeed === '1';

    if (sessionSeed) {
        window.sessionStorage.setItem(sessionKey, '1');
        return true;
    }

    if (!hasTabSession) {
        const logoutUrl = body.dataset.forceLogoutUrl || '/logout/';
        window.location.replace(logoutUrl);
        return false;
    }

    return true;
}

function initChatAutoScroll() {
    const threads = document.querySelectorAll('.chat-thread');
    threads.forEach((thread) => {
        thread.scrollTop = thread.scrollHeight;
    });
}

function initAiHelperChat() {
    const widget = document.getElementById('aiHelperWidget');
    const launcher = document.getElementById('aiHelperLauncher');
    const closeButton = document.getElementById('aiHelperClose');
    const form = document.getElementById('aiHelperForm');
    const thread = document.getElementById('aiHelperThread');
    if (!widget || !launcher || !closeButton || !form || !thread) {
        return null;
    }

    const textarea = form.querySelector('textarea[name="message"]');
    if (!textarea) {
        return null;
    }

    const openTriggers = [...document.querySelectorAll('[data-open-ai-helper]')];
    const currentUser = document.body.dataset.currentUser || 'anonymous';
    const openKey = `atlas_ai_widget_open:${currentUser}`;
    const historyKey = `atlas_ai_widget_history:${currentUser}`;

    const normalizeHistory = (raw) => {
        if (!Array.isArray(raw)) {
            return [];
        }
        return raw
            .filter((item) => item && (item.role === 'user' || item.role === 'assistant') && typeof item.text === 'string')
            .map((item) => ({ role: item.role, text: item.text.trim().slice(0, 1200) }))
            .filter((item) => item.text.length > 0)
            .slice(-40);
    };

    const loadHistory = () => {
        try {
            const parsed = JSON.parse(window.localStorage.getItem(historyKey) || '[]');
            return normalizeHistory(parsed);
        } catch (error) {
            return [];
        }
    };

    const saveHistory = (historyRows) => {
        window.localStorage.setItem(historyKey, JSON.stringify(normalizeHistory(historyRows)));
    };

    let history = loadHistory();
    if (history.length === 0) {
        history = [
            {
                role: 'assistant',
                text: 'Hi. I am AtlasBoard AI Helper. Ask me where to go or how to use features.',
            },
        ];
        saveHistory(history);
    }

    const appendBubble = (role, text, persist = true) => {
        const line = document.createElement('div');
        line.className = `chat-line ${role === 'user' ? 'mine' : 'theirs'}`;

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';

        const author = document.createElement('div');
        author.className = 'chat-author';
        author.textContent = role === 'user' ? 'You' : 'AI Helper';

        const paragraph = document.createElement('p');
        paragraph.textContent = text;

        bubble.appendChild(author);
        bubble.appendChild(paragraph);
        line.appendChild(bubble);
        thread.appendChild(line);
        thread.scrollTop = thread.scrollHeight;

        if (persist) {
            history.push({ role, text: String(text || '').slice(0, 1200) });
            history = normalizeHistory(history);
            saveHistory(history);
        }
    };

    const renderHistory = () => {
        thread.innerHTML = '';
        history.forEach((item) => appendBubble(item.role, item.text, false));
    };

    const setOpen = (nextOpen) => {
        const isOpen = Boolean(nextOpen);
        widget.classList.toggle('open', isOpen);
        widget.hidden = !isOpen;
        launcher.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        window.localStorage.setItem(openKey, isOpen ? '1' : '0');
        if (isOpen) {
            setTimeout(() => textarea.focus(), 30);
        }
    };

    launcher.addEventListener('click', () => setOpen(true));
    closeButton.addEventListener('click', () => setOpen(false));
    openTriggers.forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            setOpen(true);
        });
    });

    renderHistory();
    const shouldAutoOpen = window.localStorage.getItem(openKey) === '1' || document.body.classList.contains('page-ai-helper');
    setOpen(shouldAutoOpen);

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const message = textarea.value.trim();
        if (!message) {
            return;
        }

        const formData = new FormData(form);
        formData.set('message', message);
        appendBubble('user', message);
        textarea.value = '';

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                appendBubble('assistant', payload.error || 'AI Helper could not process your request.');
                return;
            }
            appendBubble('assistant', payload.reply || 'No response returned.');
            if (payload.navigate_to) {
                window.localStorage.setItem(openKey, '1');
                setTimeout(() => {
                    window.location.assign(payload.navigate_to);
                }, 700);
            }
        } catch (error) {
            appendBubble('assistant', 'Network error. Please try again.');
        }
    });

    return { active: true };
}

function initFriendsPageEditMode() {
    const toggle = document.getElementById('friendsEditToggle');
    if (!toggle) {
        return null;
    }

    const editableForms = [...document.querySelectorAll('.friend-editable-form')];
    const editOnlyControls = [...document.querySelectorAll('.friend-edit-only')];
    const storageKey = `atlasboard_friends_edit_mode:${window.location.pathname}`;
    let editMode = window.localStorage.getItem(storageKey) === '1';

    const applyMode = () => {
        toggle.checked = editMode;
        document.body.classList.toggle('friends-edit-on', editMode);
        document.body.classList.toggle('friends-edit-off', !editMode);

        editableForms.forEach((form) => {
            form.querySelectorAll('input, textarea, select, button').forEach((field) => {
                if (field.type === 'hidden') {
                    return;
                }
                field.disabled = !editMode;
            });
        });

        editOnlyControls.forEach((control) => {
            control.hidden = !editMode;
        });
    };

    toggle.addEventListener('change', () => {
        editMode = toggle.checked;
        window.localStorage.setItem(storageKey, editMode ? '1' : '0');
        applyMode();
    });

    applyMode();
    return { isEditMode: () => editMode };
}

function initHomeCardEditMode() {
    const toggleWrap = document.getElementById('homeCardEditToggleWrap');
    const toggle = document.getElementById('homeCardEditToggle');
    if (!toggleWrap || !toggle) {
        return null;
    }

    const editBlocks = [...document.querySelectorAll('.home-edit-only')];
    const editForms = [...document.querySelectorAll('[data-home-edit-form]')];
    if (editBlocks.length === 0) {
        toggleWrap.hidden = true;
        return null;
    }

    const storageKey = `atlasboard_home_card_edit_mode:${window.location.pathname}`;
    let editMode = window.localStorage.getItem(storageKey) === '1';

    const formFields = (form) =>
        [...form.querySelectorAll('input, textarea, select, button')].filter((field) => field.type !== 'hidden');

    const snapshotFormValues = (form) => {
        formFields(form).forEach((field) => {
            if (field.type === 'checkbox') {
                field.dataset.originalValue = field.checked ? '1' : '0';
                return;
            }
            field.dataset.originalValue = field.value;
        });
    };

    const resetFormValues = (form) => {
        formFields(form).forEach((field) => {
            const originalValue = field.dataset.originalValue || '';
            if (field.type === 'checkbox') {
                field.checked = originalValue === '1';
                return;
            }
            field.value = originalValue;
        });
    };

    const setFormEnabled = (form, enabled) => {
        formFields(form).forEach((field) => {
            field.disabled = !enabled;
        });
    };

    editForms.forEach((form) => snapshotFormValues(form));

    const applyMode = () => {
        if (!editMode) {
            editForms.forEach((form) => resetFormValues(form));
        }
        editForms.forEach((form) => setFormEnabled(form, editMode));
        toggle.checked = editMode;
        document.body.classList.toggle('home-card-edit-on', editMode);
        document.body.classList.toggle('home-card-edit-off', !editMode);
    };

    toggle.addEventListener('change', () => {
        editMode = toggle.checked;
        window.localStorage.setItem(storageKey, editMode ? '1' : '0');
        applyMode();
    });

    applyMode();
    return { isEditMode: () => editMode };
}

function initSidebarMenu() {
    const sidebar = document.getElementById('sidebar');
    const toggleButton = document.getElementById('sidebarToggle');
    const overlay = document.getElementById('sidebarOverlay');

    const isMobile = () => window.innerWidth <= 768;

    const setSidebarOpen = (open) => {
        if (!sidebar || !toggleButton || !overlay) {
            return;
        }

        const shouldOpen = isMobile() && open;
        sidebar.classList.toggle('open', shouldOpen);
        toggleButton.setAttribute('aria-expanded', String(shouldOpen));
        overlay.hidden = !shouldOpen;
    };

    if (sidebar && toggleButton && overlay) {
        toggleButton.addEventListener('click', () => {
            const currentlyOpen = sidebar.classList.contains('open');
            setSidebarOpen(!currentlyOpen);
        });

        overlay.addEventListener('click', () => setSidebarOpen(false));

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                setSidebarOpen(false);
            }
        });

        window.addEventListener('resize', () => {
            if (!isMobile()) {
                setSidebarOpen(false);
            }
        });
    }
}

function initViewButtons() {
    document.querySelectorAll('.view-btn').forEach((button) => {
        button.addEventListener('click', () => {
            const description = button.nextElementSibling;
            if (!description) {
                return;
            }
            description.hidden = !description.hidden;
        });
    });
}

function initPageAdminEditMode() {
    const isAdmin = document.body.dataset.isAdmin === '1';
    const toggleWrap = document.getElementById('pageAdminToggleWrap');
    const toggle = document.getElementById('adminEditToggle');
    const editableForms = [...document.querySelectorAll('.admin-editable-form')];
    const editOnlyBlocks = [...document.querySelectorAll('.admin-edit-only')];
    const adminRows = [...document.querySelectorAll('.admin-edit-row [data-field]')];
    const hasEditableControls = editableForms.length > 0 || editOnlyBlocks.length > 0 || adminRows.length > 0;

    if (!isAdmin || !toggleWrap || !toggle || !hasEditableControls) {
        if (toggleWrap) {
            toggleWrap.hidden = true;
        }
        return null;
    }

    toggleWrap.hidden = false;

    const storageKey = `atlasboard_admin_edit_mode:${window.location.pathname}`;
    let editMode = window.localStorage.getItem(storageKey) === '1';
    const onModeChangeHandlers = [];
    const onBeforeDisableHandlers = [];

    const applyFormState = (enabled) => {
        editableForms.forEach((form) => {
            form.querySelectorAll('input, textarea, select, button').forEach((field) => {
                if (field.type === 'hidden') {
                    return;
                }
                if (field.dataset.locked === '1') {
                    field.disabled = true;
                    return;
                }
                field.disabled = !enabled;
            });
        });
    };

    const applyMode = () => {
        toggle.checked = editMode;
        document.body.classList.toggle('admin-edit-on', editMode);
        document.body.classList.toggle('admin-edit-off', !editMode);
        applyFormState(editMode);
        onModeChangeHandlers.forEach((handler) => handler(editMode));
    };

    const setMode = async (enabled) => {
        if (enabled === editMode) {
            return true;
        }

        if (!enabled) {
            for (const handler of onBeforeDisableHandlers) {
                const ok = await handler();
                if (!ok) {
                    return false;
                }
            }
        }

        editMode = enabled;
        window.localStorage.setItem(storageKey, editMode ? '1' : '0');
        applyMode();
        return true;
    };

    toggle.addEventListener('change', async () => {
        const requestedMode = toggle.checked;
        const ok = await setMode(requestedMode);
        if (!ok) {
            toggle.checked = !requestedMode;
        }
    });

    applyMode();

    return {
        isEditMode: () => editMode,
        onModeChange: (handler) => onModeChangeHandlers.push(handler),
        onBeforeDisable: (handler) => onBeforeDisableHandlers.push(handler),
    };
}

function initAdminCenterTables() {
    const root = document.getElementById('adminCenterRoot');
    if (!root) {
        return null;
    }

    const rows = [...root.querySelectorAll('.admin-edit-row')];
    if (rows.length === 0) {
        return null;
    }

    const groupToggles = [...root.querySelectorAll('[data-admin-group-toggle]')];
    if (groupToggles.length === 0) {
        return null;
    }
    const groupSaveButtons = [...root.querySelectorAll('[data-admin-group-save]')];

    const csrfToken = getCookie('csrftoken');
    const groupModes = {};

    const rowGroup = (row) => row.dataset.editGroup || 'default';
    const isGroupEditable = (group) => Boolean(groupModes[group]);
    const getGroupSaveButton = (group) =>
        groupSaveButtons.find((button) => button.dataset.adminGroupSave === group) || null;

    const hasDirtyRows = (group = null) =>
        rows.some((row) => row.isConnected && row.dataset.dirty === '1' && (!group || rowGroup(row) === group));

    const applyGroupSaveState = (group) => {
        const saveButton = getGroupSaveButton(group);
        if (!saveButton) {
            return;
        }
        const editable = isGroupEditable(group);
        const dirty = hasDirtyRows(group);
        saveButton.hidden = !editable;
        saveButton.disabled = !editable || !dirty;
        saveButton.textContent = dirty ? 'Save' : 'Saved';
    };

    const applyGroupModeToRows = (group) => {
        rows
            .filter((row) => rowGroup(row) === group)
            .forEach((row) => applyRowMode(row, isGroupEditable(group)));
    };

    const setGroupMode = (group, enabled) => {
        groupModes[group] = enabled;
        window.localStorage.setItem(`atlasboard_admin_table_mode:${window.location.pathname}:${group}`, enabled ? '1' : '0');
        applyGroupModeToRows(group);
        applyGroupSaveState(group);
    };

    const getFieldValue = (field) => {
        if (field.type === 'checkbox') {
            return field.checked ? '1' : '0';
        }
        return field.value.trim();
    };

    const setFieldValue = (field, value) => {
        if (field.type === 'checkbox') {
            field.checked = value === '1' || value === 'true';
            return;
        }
        field.value = value;
    };

    const rowFields = (row) => [...row.querySelectorAll('[data-field]')];

    const setRowStatus = (row, text, isError = false) => {
        const status = row.querySelector('.admin-row-status');
        if (!status) {
            return;
        }
        status.textContent = text;
        status.classList.toggle('error', isError);
    };

    const isRowDirty = (row) =>
        rowFields(row).some((field) => getFieldValue(field) !== (field.dataset.originalValue || ''));

    const setRowDirty = (row) => {
        const dirty = isRowDirty(row);
        row.dataset.dirty = dirty ? '1' : '0';
        row.classList.toggle('dirty', dirty);
        setRowStatus(row, dirty ? 'Unsaved changes' : 'Saved', false);
        const canEdit = isGroupEditable(rowGroup(row));
        row.querySelectorAll('.admin-undo-btn').forEach((button) => {
            button.disabled = !dirty || !canEdit;
        });
        applyGroupSaveState(rowGroup(row));
    };

    const resetRow = (row) => {
        rowFields(row).forEach((field) => {
            setFieldValue(field, field.dataset.originalValue || '');
        });
        setRowDirty(row);
    };

    const resetGroupRows = (group) => {
        rows
            .filter((row) => row.isConnected && rowGroup(row) === group)
            .forEach((row) => resetRow(row));
        applyGroupSaveState(group);
    };

    const updateOriginalValues = (row) => {
        rowFields(row).forEach((field) => {
            field.dataset.originalValue = getFieldValue(field);
        });
        setRowDirty(row);
    };

    const rowPayload = (row) => {
        const payload = new FormData();
        rowFields(row).forEach((field) => {
            payload.append(field.dataset.field, getFieldValue(field));
        });
        return payload;
    };

    const applyRowMode = (row, enabled) => {
        rowFields(row).forEach((field) => {
            if (field.dataset.locked === '1') {
                field.disabled = true;
                return;
            }
            field.disabled = !enabled;
        });
        row.querySelectorAll('.admin-undo-btn').forEach((button) => {
            button.disabled = !enabled || row.dataset.dirty !== '1';
        });
        row.querySelectorAll('.admin-action-on-edit').forEach((button) => {
            button.hidden = !enabled;
            button.disabled = !enabled;
        });
    };

    rows.forEach((row) => {
        rowFields(row).forEach((field) => {
            field.dataset.originalValue = getFieldValue(field);
            const eventName = field.type === 'checkbox' || field.tagName === 'SELECT' ? 'change' : 'input';
            field.addEventListener(eventName, () => {
                if (!isGroupEditable(rowGroup(row))) {
                    return;
                }
                setRowDirty(row);
            });
        });

        row.querySelectorAll('.admin-undo-btn').forEach((button) => {
            button.addEventListener('click', () => {
                if (!isGroupEditable(rowGroup(row))) {
                    return;
                }
                resetRow(row);
            });
        });

        row.querySelectorAll('.admin-delete-btn').forEach((button) => {
            button.addEventListener('click', async () => {
                if (!isGroupEditable(rowGroup(row))) {
                    return;
                }
                if (!confirm('Delete this post?')) {
                    return;
                }

                try {
                    const response = await fetch(row.dataset.deleteUrl, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.ok) {
                        setRowStatus(row, payload.error || 'Delete failed', true);
                        return;
                    }
                    row.remove();
                    applyGroupSaveState(rowGroup(row));
                } catch (error) {
                    setRowStatus(row, 'Delete failed', true);
                }
            });
        });

        setRowDirty(row);
        applyRowMode(row, false);
    });

    groupToggles.forEach((toggle) => {
        const group = toggle.dataset.adminGroupToggle;
        const saved = window.localStorage.getItem(`atlasboard_admin_table_mode:${window.location.pathname}:${group}`) === '1';
        groupModes[group] = saved;
        toggle.checked = saved;
        applyGroupModeToRows(group);
        applyGroupSaveState(group);

        toggle.addEventListener('change', () => {
            const enableEdit = toggle.checked;
            if (!enableEdit) {
                resetGroupRows(group);
            }
            setGroupMode(group, enableEdit);
        });
    });

    groupSaveButtons.forEach((button) => {
        const group = button.dataset.adminGroupSave;
        button.hidden = !isGroupEditable(group);
        button.disabled = true;
        button.addEventListener('click', async () => {
            if (!isGroupEditable(group)) {
                return;
            }
            button.disabled = true;
            await saveDirtyRows(group);
            applyGroupSaveState(group);
        });
    });

    const saveRow = async (row) => {
        if (row.dataset.dirty !== '1') {
            return true;
        }

        try {
            const response = await fetch(row.dataset.updateUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: rowPayload(row),
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                setRowStatus(row, payload.error || 'Save failed', true);
                return false;
            }

            if (row.dataset.rowType === 'card' && payload.tags !== undefined) {
                const tagField = row.querySelector('[data-field="tags"]');
                if (tagField) {
                    tagField.value = payload.tags;
                }
            }
            updateOriginalValues(row);
            setRowStatus(row, 'Saved', false);
            return true;
        } catch (error) {
            setRowStatus(row, 'Save failed', true);
            return false;
        }
    };

    const saveDirtyRows = async (group = null) => {
        const dirtyRows = rows.filter(
            (row) => row.isConnected && row.dataset.dirty === '1' && (!group || rowGroup(row) === group)
        );
        for (const row of dirtyRows) {
            const ok = await saveRow(row);
            if (!ok) {
                return false;
            }
        }
        return true;
    };

    document.addEventListener(
        'click',
        (event) => {
            const link = event.target.closest('a[href]');
            if (!link || !hasDirtyRows() || event.defaultPrevented) {
                return;
            }
            if (link.target === '_blank' || link.hasAttribute('download')) {
                return;
            }

            const href = link.getAttribute('href');
            if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:')) {
                return;
            }

            event.preventDefault();
            const discard = confirm('You have unsaved changes. Leave this page and discard them?');
            if (discard) {
                window.location.assign(link.href);
            }
        },
        true
    );

    window.addEventListener('beforeunload', (event) => {
        if (!hasDirtyRows()) {
            return;
        }
        event.preventDefault();
        event.returnValue = '';
    });

    return {
        saveDirtyRows,
    };
}

function getCookie(name) {
    const cookieValue = document.cookie
        .split(';')
        .map((cookie) => cookie.trim())
        .find((cookie) => cookie.startsWith(`${name}=`));
    if (!cookieValue) {
        return '';
    }
    return decodeURIComponent(cookieValue.split('=')[1]);
}
