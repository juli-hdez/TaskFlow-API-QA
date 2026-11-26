const USERS_KEY = "taskflow.users";
const SESSION_KEY = "taskflow.session";
const PASSWORD_ITERATIONS = 120000;

const authView = document.querySelector("#authView");
const appView = document.querySelector("#appView");
const authForm = document.querySelector("#authForm");
const authUsername = document.querySelector("#authUsername");
const authPassword = document.querySelector("#authPassword");
const authRegisterHelp = document.querySelectorAll(".auth-register-help");
const confirmPassword = document.querySelector("#confirmPassword");
const confirmPasswordField = document.querySelector("#confirmPasswordField");
const authMessage = document.querySelector("#authMessage");
const authSubmit = document.querySelector("#authSubmit");
const loginTab = document.querySelector("#loginTab");
const registerTab = document.querySelector("#registerTab");
const taskDialog = document.querySelector("#taskDialog");
const taskForm = document.querySelector("#taskForm");
const taskMessage = document.querySelector("#taskMessage");
const taskTitleInput = document.querySelector("#taskTitle");
const taskDescriptionInput = document.querySelector("#taskDescription");
const taskDueDateInput = document.querySelector("#taskDueDate");
const taskList = document.querySelector("#taskList");
const searchInput = document.querySelector("#searchInput");
const statusFilter = document.querySelector("#statusFilter");
const toast = document.querySelector("#toast");

let authMode = "login";
let currentUser = "";
let toastTimeout;

const taskTextPattern = /^[\p{Script=Latin} ,;.]*$/u;

const statusLabels = {
    pending: "Pendiente",
    "in-progress": "En progreso",
    completed: "Completada"
};

const priorityLabels = {
    low: "Prioridad baja",
    medium: "Prioridad media",
    high: "Prioridad alta"
};

function readUsers() {
    return JSON.parse(localStorage.getItem(USERS_KEY) || "[]");
}

function saveUsers(users) {
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function tasksKey() {
    return `taskflow.tasks:${currentUser}`;
}

function readTasks() {
    return JSON.parse(localStorage.getItem(tasksKey()) || "[]");
}

function saveTasks(tasks) {
    localStorage.setItem(tasksKey(), JSON.stringify(tasks));
}

function bytesToHex(bytes) {
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let index = 0; index < bytes.length; index += 1) {
        bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
    }
    return bytes;
}

function isValidPassword(password) {
    if (!/^[A-Za-z0-9._@-]+$/.test(password)) {
        return false;
    }

    const letters = password.match(/[A-Za-z]/g) || [];
    const numbers = password.match(/[0-9]/g) || [];
    const specialCharacters = password.match(/[._@-]/g) || [];
    return letters.length >= 8 && numbers.length >= 2 && specialCharacters.length >= 1;
}

async function hashPassword(password, salt) {
    if (!window.crypto || !window.crypto.subtle) {
        throw new Error("La protección local de contraseñas no está disponible. Abre el proyecto con Live Server.");
    }

    const key = await window.crypto.subtle.importKey(
        "raw",
        new TextEncoder().encode(password),
        "PBKDF2",
        false,
        ["deriveBits"]
    );
    const result = await window.crypto.subtle.deriveBits(
        {
            name: "PBKDF2",
            salt,
            iterations: PASSWORD_ITERATIONS,
            hash: "SHA-256"
        },
        key,
        256
    );
    return new Uint8Array(result);
}

function setAuthMode(mode) {
    authMode = mode;
    const isRegistering = mode === "register";
    loginTab.classList.toggle("is-active", !isRegistering);
    registerTab.classList.toggle("is-active", isRegistering);
    loginTab.setAttribute("aria-selected", String(!isRegistering));
    registerTab.setAttribute("aria-selected", String(isRegistering));
    confirmPasswordField.classList.toggle("hidden", !isRegistering);
    authRegisterHelp.forEach((help) => help.classList.toggle("hidden", !isRegistering));
    confirmPassword.required = isRegistering;
    authPassword.autocomplete = isRegistering ? "new-password" : "current-password";
    authSubmit.textContent = isRegistering ? "Crear cuenta" : "Entrar";
    authMessage.textContent = "";
}

function showApp(username) {
    currentUser = username;
    sessionStorage.setItem(SESSION_KEY, username);
    authView.classList.add("hidden");
    appView.classList.remove("hidden");
    document.querySelector("#userHandle").textContent = username;
    document.querySelector("#userName").textContent = username;
    renderTasks();
}

function showAuth() {
    currentUser = "";
    sessionStorage.removeItem(SESSION_KEY);
    appView.classList.add("hidden");
    authView.classList.remove("hidden");
    authForm.reset();
    setAuthMode("login");
    authUsername.focus();
}

function showToast(message) {
    window.clearTimeout(toastTimeout);
    toast.textContent = message;
    toast.classList.add("is-visible");
    toastTimeout = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function createBadge(text, className) {
    const badge = document.createElement("span");
    badge.className = `task-badge ${className}`;
    badge.textContent = text;
    return badge;
}

function formatDueDate(date) {
    return new Date(`${date}T00:00:00`).toLocaleDateString("es", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}

function localDateString(date = new Date()) {
    return [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0")
    ].join("-");
}

function taskCreationDate(task) {
    return localDateString(new Date(task.createdAt));
}

function isOverdue(task) {
    if (!task.dueDate || task.status === "completed") {
        return false;
    }
    const today = new Date();
    const todayString = [
        today.getFullYear(),
        String(today.getMonth() + 1).padStart(2, "0"),
        String(today.getDate()).padStart(2, "0")
    ].join("-");
    return task.dueDate < todayString;
}

function renderTask(task) {
    const card = document.createElement("article");
    card.className = "task-card";

    const main = document.createElement("div");
    main.className = "task-main";

    const titleRow = document.createElement("div");
    titleRow.className = "task-title-row";
    const title = document.createElement("h3");
    title.className = "task-title";
    title.textContent = task.title;
    titleRow.append(title);
    titleRow.append(createBadge(statusLabels[task.status], `status-${task.status}`));
    titleRow.append(createBadge(priorityLabels[task.priority], `priority-${task.priority}`));
    main.append(titleRow);

    if (task.description) {
        const description = document.createElement("p");
        description.className = "task-description";
        description.textContent = task.description;
        main.append(description);
    }

    if (task.dueDate) {
        const metadata = document.createElement("div");
        metadata.className = "task-meta";
        const dueDate = document.createElement("span");
        dueDate.textContent = `Fecha límite: ${formatDueDate(task.dueDate)}`;
        if (isOverdue(task)) {
            dueDate.classList.add("overdue-label");
            dueDate.textContent += " · Vencida";
        }
        metadata.append(dueDate);
        main.append(metadata);
    }

    const actions = document.createElement("div");
    actions.className = "task-actions";

    const editButton = document.createElement("button");
    editButton.className = "icon-button";
    editButton.type = "button";
    editButton.dataset.action = "edit";
    editButton.dataset.id = task.id;
    editButton.setAttribute("aria-label", `Editar ${task.title}`);
    editButton.textContent = "✎";

    const deleteButton = document.createElement("button");
    deleteButton.className = "icon-button delete-button";
    deleteButton.type = "button";
    deleteButton.dataset.action = "delete";
    deleteButton.dataset.id = task.id;
    deleteButton.setAttribute("aria-label", `Eliminar ${task.title}`);
    deleteButton.textContent = "⌫";

    actions.append(editButton, deleteButton);
    card.append(main, actions);
    return card;
}

function renderEmptyState(hasTasks, hasFilters) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const heading = document.createElement("strong");
    const message = document.createElement("p");

    if (!hasTasks) {
        heading.textContent = "Aún no tienes tareas";
        message.textContent = "Crea tu primera tarea para empezar a organizarte.";
    } else if (hasFilters) {
        heading.textContent = "No encontramos tareas";
        message.textContent = "Prueba con otros términos o cambia los filtros.";
    } else {
        heading.textContent = "Todo listo por aquí";
        message.textContent = "No hay tareas para mostrar.";
    }

    empty.append(heading, message);
    return empty;
}

function renderTasks() {
    const tasks = readTasks();
    const searchTerm = searchInput.value.trim().toLocaleLowerCase();
    const selectedStatus = statusFilter.value;
    const visibleTasks = tasks
        .filter((task) => selectedStatus === "all" || task.status === selectedStatus)
        .filter((task) => `${task.title} ${task.description}`.toLocaleLowerCase().includes(searchTerm))
        .sort((first, second) => second.createdAt.localeCompare(first.createdAt));

    document.querySelector("#totalCount").textContent = String(tasks.length);
    document.querySelector("#activeCount").textContent = String(tasks.filter((task) => task.status === "in-progress").length);
    document.querySelector("#completedCount").textContent = String(tasks.filter((task) => task.status === "completed").length);
    document.querySelector("#overdueCount").textContent = String(tasks.filter(isOverdue).length);

    taskList.replaceChildren();
    if (visibleTasks.length === 0) {
        taskList.append(renderEmptyState(tasks.length > 0, Boolean(searchTerm) || selectedStatus !== "all"));
        return;
    }

    visibleTasks.forEach((task) => taskList.append(renderTask(task)));
}

function openTaskDialog(task) {
    taskForm.reset();
    taskMessage.textContent = "";
    taskDueDateInput.min = task ? taskCreationDate(task) : localDateString();
    document.querySelector("#taskId").value = task ? task.id : "";
    document.querySelector("#dialogTitle").textContent = task ? "Editar tarea" : "Nueva tarea";
    taskTitleInput.value = task ? task.title : "";
    taskDescriptionInput.value = task ? task.description : "";
    document.querySelector("#taskStatus").value = task ? task.status : "pending";
    document.querySelector("#taskPriority").value = task ? task.priority : "medium";
    taskDueDateInput.value = task ? task.dueDate : "";
    taskDialog.showModal();
    document.querySelector("#taskTitle").focus();
}

loginTab.addEventListener("click", () => setAuthMode("login"));
registerTab.addEventListener("click", () => setAuthMode("register"));

authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    authMessage.textContent = "";
    const username = authUsername.value.trim().toLocaleLowerCase();
    const password = authPassword.value;
    const isRegistering = authMode === "register";

    if (!/^[a-z0-9._-]{3,20}$/.test(username)) {
        authMessage.textContent = isRegistering
            ? "Lo sentimos, nombre de usuario no válido"
            : "Nombre de usuario o contraseña incorrectos.";
        return;
    }

    authSubmit.disabled = true;
    try {
        const users = readUsers();
        const existingUser = users.find((user) => user.username === username);

        if (isRegistering) {
            if (existingUser) {
                authMessage.textContent = "Lo sentimos, este nombre de usuario ya está en uso";
                return;
            }
            if (!isValidPassword(password)) {
                authMessage.textContent = "Lo sentimos, tu contraseña no cumple con los parámetros solicitados";
                return;
            }
            if (password !== confirmPassword.value) {
                authMessage.textContent = "Lo sentimos, las contraseñas no concuerdan";
                return;
            }

            const salt = window.crypto.getRandomValues(new Uint8Array(16));
            const passwordHash = await hashPassword(password, salt);
            users.push({
                username,
                salt: bytesToHex(salt),
                passwordHash: bytesToHex(passwordHash)
            });
            saveUsers(users);
            showApp(username);
            showToast("Cuenta creada correctamente.");
            return;
        }

        if (!isValidPassword(password) || !existingUser) {
            authMessage.textContent = "Nombre de usuario o contraseña incorrectos.";
            return;
        }

        const passwordHash = await hashPassword(password, hexToBytes(existingUser.salt));
        if (bytesToHex(passwordHash) !== existingUser.passwordHash) {
            authMessage.textContent = "Nombre de usuario o contraseña incorrectos.";
            return;
        }

        showApp(username);
    } catch (error) {
        authMessage.textContent = error instanceof Error
            ? error.message
            : "No se pudo completar la operación. Inténtalo de nuevo.";
    } finally {
        authSubmit.disabled = false;
    }
});

document.querySelector("#logoutButton").addEventListener("click", showAuth);
document.querySelector("#newTaskButton").addEventListener("click", () => openTaskDialog(null));
document.querySelector("#closeDialogButton").addEventListener("click", () => taskDialog.close());
document.querySelector("#cancelTaskButton").addEventListener("click", () => taskDialog.close());
searchInput.addEventListener("input", renderTasks);
statusFilter.addEventListener("change", renderTasks);

taskForm.addEventListener("submit", (event) => {
    event.preventDefault();
    taskMessage.textContent = "";

    const title = taskTitleInput.value.trim().normalize("NFC");
    if (!title) {
        taskMessage.textContent = "Escribe un título para la tarea.";
        return;
    }

    const tasks = readTasks();
    const taskId = document.querySelector("#taskId").value;
    const existingTask = tasks.find((task) => task.id === taskId);
    const description = taskDescriptionInput.value.trim().normalize("NFC");
    if (title.length > 100 || !taskTextPattern.test(title)) {
        taskMessage.textContent = "El título solo puede contener hasta 100 caracteres: letras latinas, espacios, comas, puntos y punto y coma.";
        return;
    }
    if (description.length > 500 || !taskTextPattern.test(description)) {
        taskMessage.textContent = "La descripción solo puede contener hasta 500 caracteres: letras latinas, espacios, comas, puntos y punto y coma.";
        return;
    }

    const dueDate = taskDueDateInput.value;
    const earliestDueDate = existingTask ? taskCreationDate(existingTask) : localDateString();
    if (dueDate && dueDate < earliestDueDate) {
        taskMessage.textContent = "La fecha límite debe ser igual o posterior a la fecha de creación de la tarea.";
        return;
    }

    const task = {
        id: taskId || (window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
        title,
        description,
        status: document.querySelector("#taskStatus").value,
        priority: document.querySelector("#taskPriority").value,
        dueDate,
        createdAt: existingTask ? existingTask.createdAt : new Date().toISOString()
    };

    const updatedTasks = existingTask
        ? tasks.map((item) => item.id === taskId ? task : item)
        : [task, ...tasks];

    saveTasks(updatedTasks);
    taskDialog.close();
    renderTasks();
    showToast(existingTask ? "Tarea actualizada." : "Tarea creada.");
});

taskList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) {
        return;
    }

    const tasks = readTasks();
    const task = tasks.find((item) => item.id === button.dataset.id);
    if (!task) {
        return;
    }

    if (button.dataset.action === "edit") {
        openTaskDialog(task);
        return;
    }

    if (button.dataset.action === "delete" && window.confirm(`¿Eliminar la tarea "${task.title}"?`)) {
        saveTasks(tasks.filter((item) => item.id !== task.id));
        renderTasks();
        showToast("Tarea eliminada.");
    }
});

const storedSession = sessionStorage.getItem(SESSION_KEY);
if (storedSession && readUsers().some((user) => user.username === storedSession)) {
    showApp(storedSession);
}
