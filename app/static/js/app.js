/**
 * Luke - SaaS Agile Kanban & Multi-Tenant
 * Frontend JavaScript vanilla réactif ultra-complet avec SortableJS
 */

const LukeApp = {
  state: {
    companies: [],
    currentCompanyId: null,
    currentCompany: null,
    
    users: [],
    currentUserId: null,
    currentUser: null,
    
    projects: [],
    currentProjectId: null,
    currentProject: null,
    
    tasks: [],
    currentEditingTaskId: null,
    currentEditingTask: null,
    
    filters: {
      search: "",
      assigneeId: "",
      priority: "",
      tag: "",
      onlyMine: false,
    },
    
    activeTab: "kanban", // "kanban", "list", "projects", "team", "architecture"
    analyticsOpen: false,
    sortableInstances: []
  },

  // --------------------------------------------------------------------------
  // 1. Initialisation
  // --------------------------------------------------------------------------
  async init() {
    this.setupEventListeners();
    this.setupKeyboardShortcuts();
    await this.loadCompanies();
  },

  // Helper pour les appels API avec headers d'isolation Multi-Tenant
  async api(endpoint, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {})
    };

    if (this.state.currentCompanyId) {
      headers["X-Company-Id"] = this.state.currentCompanyId;
    }
    if (this.state.currentUserId) {
      headers["X-User-Id"] = this.state.currentUserId;
    }

    try {
      const response = await fetch(endpoint, {
        ...options,
        headers
      });

      // Si téléchargement de fichier
      const disposition = response.headers.get("content-disposition");
      if (disposition && disposition.includes("attachment")) {
        const blob = await response.blob();
        return { isBlob: true, blob, filename: disposition.split("filename=")[1]?.replace(/"/g, "") || "export" };
      }

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || data.message || `Erreur HTTP ${response.status}`);
      }
      return data;
    } catch (err) {
      this.showToast(err.message, "error");
      throw err;
    }
  },

  // --------------------------------------------------------------------------
  // 2. Gestion des Entreprises (Companies)
  // --------------------------------------------------------------------------
  async loadCompanies(targetId = null) {
    try {
      const companies = await this.api("/api/companies");
      this.state.companies = companies;

      if (companies.length === 0) {
        this.renderNoCompanyState();
        return;
      }

      let selected = companies.find(c => c.id === targetId);
      if (!selected) {
        selected = companies.find(c => c.id === this.state.currentCompanyId) || companies[0];
      }

      await this.setCompany(selected.id);
    } catch (err) {
      console.error("Erreur chargement entreprises:", err);
    }
  },

  async setCompany(companyId) {
    this.state.currentCompanyId = companyId;
    this.state.currentCompany = this.state.companies.find(c => c.id === companyId);
    
    // Réinitialisation des filtres
    this.state.filters.onlyMine = false;
    this.state.filters.assigneeId = "";
    this.state.filters.priority = "";
    this.state.filters.tag = "";
    this.state.filters.search = "";

    this.renderCompanyUI();

    // Charger les utilisateurs et les projets en parallèle
    await Promise.all([
      this.loadUsers(),
      this.loadProjects()
    ]);
  },

  renderCompanyUI() {
    const comp = this.state.currentCompany;
    if (!comp) return;

    const nameEl = document.getElementById("header-company-name");
    const planEl = document.getElementById("header-company-plan");
    if (nameEl) nameEl.textContent = comp.name;
    if (planEl) {
      planEl.textContent = comp.plan;
      planEl.className = "text-[10px] font-bold px-1.5 py-0.2 rounded " + 
        (comp.plan === "ENTERPRISE" ? "bg-purple-900/60 text-purple-300 border border-purple-500/30" :
         comp.plan === "PRO" ? "bg-indigo-900/60 text-indigo-300 border border-indigo-500/30" :
         "bg-slate-800 text-slate-300 border border-slate-700");
    }

    const listEl = document.getElementById("companies-dropdown-list");
    if (listEl) {
      listEl.innerHTML = this.state.companies.map(c => `
        <button onclick="LukeApp.setCompany('${c.id}')" class="w-full text-left px-3 py-2 rounded-lg flex items-center justify-between hover:bg-slate-800 transition ${c.id === comp.id ? 'bg-indigo-950/50 text-indigo-300 font-medium' : 'text-slate-300'}">
          <div class="flex items-center space-x-2.5 truncate">
            <span class="w-2 h-2 rounded-full ${c.id === comp.id ? 'bg-indigo-400' : 'bg-slate-600'}"></span>
            <span class="truncate text-xs">${c.name}</span>
          </div>
          <span class="text-[10px] px-1.5 py-0.5 rounded font-mono ${c.plan === 'ENTERPRISE' ? 'bg-purple-900/50 text-purple-300' : 'bg-slate-800 text-slate-400'}">${c.plan}</span>
        </button>
      `).join("");
    }
  },

  // --------------------------------------------------------------------------
  // 3. Gestion des Utilisateurs (Users & Role Switcher)
  // --------------------------------------------------------------------------
  async loadUsers() {
    try {
      const users = await this.api("/api/users");
      this.state.users = users;

      if (users.length > 0) {
        const admin = users.find(u => u.role === "ADMIN") || users[0];
        this.setUser(admin.id);
      } else {
        this.state.currentUserId = null;
        this.state.currentUser = null;
        this.renderUserUI();
      }

      this.renderTeamTab();
    } catch (err) {
      console.error("Erreur chargement utilisateurs:", err);
    }
  },

  setUser(userId) {
    this.state.currentUserId = userId;
    this.state.currentUser = this.state.users.find(u => u.id === userId);
    this.renderUserUI();

    if (this.state.filters.onlyMine) {
      this.filterTasks();
    }
  },

  renderUserUI() {
    const user = this.state.currentUser;
    const nameEl = document.getElementById("header-user-name");
    const roleEl = document.getElementById("header-user-role");
    const avatarEl = document.getElementById("header-user-avatar");
    const commentAuthorEl = document.getElementById("commenting-as-name");

    if (!user) {
      if (nameEl) nameEl.textContent = "Aucun membre";
      if (roleEl) roleEl.textContent = "-";
      if (commentAuthorEl) commentAuthorEl.textContent = "Anonyme";
      return;
    }

    if (nameEl) nameEl.textContent = user.name;
    if (commentAuthorEl) commentAuthorEl.textContent = user.name;
    if (roleEl) {
      roleEl.textContent = user.role;
      roleEl.className = "text-[10px] font-bold px-1.5 py-0.2 rounded-full uppercase tracking-wider " +
        (user.role === "ADMIN" ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-blue-500/20 text-blue-300 border border-blue-500/30");
    }
    if (avatarEl) {
      avatarEl.style.backgroundColor = user.avatar_color || "#4F46E5";
      avatarEl.textContent = this.getInitials(user.name);
    }

    // Menu dropdown profil
    const listEl = document.getElementById("users-dropdown-list");
    if (listEl) {
      listEl.innerHTML = this.state.users.map(u => `
        <button onclick="LukeApp.setUser('${u.id}')" class="w-full text-left px-3 py-2 rounded-lg flex items-center justify-between hover:bg-slate-800 transition ${u.id === user.id ? 'bg-indigo-950/60 font-medium' : ''}">
          <div class="flex items-center space-x-2.5 truncate">
            <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow" style="background-color: ${u.avatar_color || '#4F46E5'}">
              ${this.getInitials(u.name)}
            </div>
            <span class="text-xs text-slate-200 truncate">${u.name}</span>
          </div>
          <span class="text-[9px] font-semibold px-1.5 py-0.2 rounded uppercase ${u.role === 'ADMIN' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-700 text-slate-400'}">${u.role}</span>
        </button>
      `).join("");
    }

    // Filtre collaborateur dans la toolbar
    const filterSelect = document.getElementById("filter-assignee");
    if (filterSelect) {
      const cur = filterSelect.value;
      filterSelect.innerHTML = `<option value="">Tous les collaborateurs</option>` +
        this.state.users.map(u => `<option value="${u.id}">${u.name}</option>`).join("");
      filterSelect.value = cur;
    }
  },

  // --------------------------------------------------------------------------
  // 4. Gestion des Projets (Projects)
  // --------------------------------------------------------------------------
  async loadProjects() {
    try {
      const projects = await this.api("/api/projects");
      this.state.projects = projects;

      const selector = document.getElementById("project-select");
      if (selector) {
        selector.innerHTML = projects.map(p => `
          <option value="${p.id}">${p.name}</option>
        `).join("");
      }

      if (projects.length === 0) {
        this.state.currentProjectId = null;
        this.state.currentProject = null;
        this.renderNoProjectState();
        return;
      }

      const activeProject = projects.find(p => p.id === this.state.currentProjectId) || projects[0];
      await this.setProject(activeProject.id);
      this.renderProjectsTab();
    } catch (err) {
      console.error("Erreur chargement projets:", err);
    }
  },

  async setProject(projectId) {
    this.state.currentProjectId = projectId;
    this.state.currentProject = this.state.projects.find(p => p.id === projectId);

    const selector = document.getElementById("project-select");
    if (selector && selector.value !== projectId) {
      selector.value = projectId;
    }

    const titleEl = document.getElementById("project-title-display");
    const descEl = document.getElementById("project-desc-display");
    const badgeEl = document.getElementById("project-status-badge");
    const membersEl = document.getElementById("project-members-display");

    if (this.state.currentProject) {
      if (titleEl) titleEl.textContent = this.state.currentProject.name;
      if (descEl) descEl.textContent = this.state.currentProject.description || "Aucune description fournie.";
      if (badgeEl) {
        badgeEl.textContent = this.state.currentProject.status;
        badgeEl.className = `text-[10px] font-bold px-2 py-0.5 rounded-full ${
          this.state.currentProject.status === 'ACTIVE' 
            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
            : 'bg-slate-700 text-slate-400'
        }`;
      }

      if (membersEl) {
        const members = this.state.currentProject.members || [];
        membersEl.innerHTML = members.map(m => `
          <div class="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white border-2 border-slate-900 shadow-sm" style="background-color: ${m.avatar_color || '#4F46E5'}" title="${m.name} (${m.role})">
            ${this.getInitials(m.name)}
          </div>
        `).join("");
      }
    }

    await this.loadTasks();
    if (this.state.analyticsOpen) {
      await this.loadProjectStats();
    }
  },

  onProjectSelectChange(newId) {
    this.setProject(newId);
  },

  // --------------------------------------------------------------------------
  // 5. Gestion des Tâches & Tableau Kanban
  // --------------------------------------------------------------------------
  async loadTasks() {
    if (!this.state.currentProjectId) {
      this.state.tasks = [];
      this.renderKanban();
      this.renderListView();
      return;
    }

    try {
      const tasks = await this.api(`/api/tasks?project_id=${this.state.currentProjectId}`);
      this.state.tasks = tasks;
      this.renderKanban();
      this.renderListView();
      this.updateProjectProgress();
    } catch (err) {
      console.error("Erreur chargement tâches:", err);
    }
  },

  updateProjectProgress() {
    const tasks = this.state.tasks;
    const total = tasks.length;
    const done = tasks.filter(t => t.status === "DONE").length;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;

    const barEl = document.getElementById("progress-bar-fill");
    const textEl = document.getElementById("progress-text-display");

    if (barEl) {
      barEl.style.width = `${pct}%`;
      barEl.className = `h-full rounded-full transition-all duration-500 ${
        pct === 100 ? 'bg-emerald-500' : pct >= 50 ? 'bg-indigo-500' : 'bg-amber-500'
      }`;
    }
    if (textEl) {
      textEl.textContent = `${pct}% complété (${done}/${total})`;
    }
  },

  renderKanban() {
    const columns = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"];
    const filteredTasks = this.getFilteredTasks();

    columns.forEach(colStatus => {
      const colEl = document.getElementById(`column-${colStatus}`);
      const countEl = document.getElementById(`count-${colStatus}`);
      if (!colEl) return;

      const colTasks = filteredTasks
        .filter(t => t.status === colStatus)
        .sort((a, b) => a.position - b.position);

      if (countEl) countEl.textContent = colTasks.length;

      if (colTasks.length === 0) {
        colEl.innerHTML = `
          <div class="h-32 flex flex-col items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded-xl p-4 text-center">
            <span class="text-xs">Aucune tâche</span>
          </div>
        `;
      } else {
        colEl.innerHTML = colTasks.map(task => this.renderTaskCard(task)).join("");
      }
    });

    this.initSortable();
  },

  getFilteredTasks() {
    return this.state.tasks.filter(task => {
      // Filtre "Mes tâches"
      if (this.state.filters.onlyMine && this.state.currentUserId) {
        if (task.assignee_id !== this.state.currentUserId) return false;
      }
      // Filtre collaborateur dropdown
      if (this.state.filters.assigneeId) {
        if (task.assignee_id !== this.state.filters.assigneeId) return false;
      }
      // Filtre priorité
      if (this.state.filters.priority) {
        if (task.priority !== this.state.filters.priority) return false;
      }
      // Filtre tag interactif
      if (this.state.filters.tag) {
        if (!(task.tags || []).includes(this.state.filters.tag)) return false;
      }
      // Recherche textuelle
      if (this.state.filters.search) {
        const query = this.state.filters.search.toLowerCase();
        const inTitle = task.title.toLowerCase().includes(query);
        const inDesc = (task.description || "").toLowerCase().includes(query);
        const inTags = (task.tags || []).some(t => t.toLowerCase().includes(query));
        if (!inTitle && !inDesc && !inTags) return false;
      }
      return true;
    });
  },

  renderTaskCard(task) {
    const assignee = this.state.users.find(u => u.id === task.assignee_id);
    const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== "DONE";

    // Formatage priorité
    let priorityBadge = "";
    if (task.priority === "HIGH") {
      priorityBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center space-x-1"><span>🔴</span><span>Urgent</span></span>`;
    } else if (task.priority === "MEDIUM") {
      priorityBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center space-x-1"><span>🟡</span><span>Moyenne</span></span>`;
    } else {
      priorityBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1"><span>🟢</span><span>Basse</span></span>`;
    }

    // Formatage date
    let dueDateHtml = "";
    if (task.due_date) {
      const d = new Date(task.due_date);
      const formatted = d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
      dueDateHtml = `
        <div class="flex items-center space-x-1 text-[11px] font-medium ${isOverdue ? 'text-rose-400 font-bold bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-800/40' : 'text-slate-400'}">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
          <span>${formatted}${isOverdue ? ' (En retard)' : ''}</span>
        </div>
      `;
    }

    // Formatage sous-tâches
    const subtasks = task.subtasks || [];
    let subtasksBadge = "";
    if (subtasks.length > 0) {
      const doneCount = subtasks.filter(s => s.done).length;
      const subPct = Math.round((doneCount / subtasks.length) * 100);
      subtasksBadge = `
        <div class="flex items-center space-x-1.5 text-[11px] text-slate-400 font-mono" title="${doneCount}/${subtasks.length} sous-tâches terminées">
          <span>☑️ ${doneCount}/${subtasks.length}</span>
          <div class="w-12 bg-slate-700 h-1 rounded-full overflow-hidden">
            <div class="h-full ${doneCount === subtasks.length ? 'bg-emerald-500' : 'bg-indigo-500'}" style="width: ${subPct}%"></div>
          </div>
        </div>
      `;
    }

    // Formatage commentaires
    const commentsCount = (task.comments || []).length;
    let commentsBadge = "";
    if (commentsCount > 0) {
      commentsBadge = `
        <div class="flex items-center space-x-1 text-[11px] text-slate-400" title="${commentsCount} commentaire(s)">
          <span>💬</span>
          <span>${commentsCount}</span>
        </div>
      `;
    }

    // Formatage tags interactifs
    const tagsHtml = (task.tags || []).map(tag => `
      <span onclick="event.stopPropagation(); LukeApp.filterByTag('${tag}')" class="interactive-tag text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/60">${tag}</span>
    `).join("");

    return `
      <div data-task-id="${task.id}" onclick="LukeApp.openEditTaskModal('${task.id}')" class="task-card group bg-slate-800/90 hover:bg-slate-800 border border-slate-700/70 hover:border-indigo-500/50 rounded-xl p-3.5 shadow-md hover:shadow-indigo-500/10 cursor-pointer active:cursor-grabbing transition-all duration-150 relative mb-3">
        <!-- Priorité & Actions -->
        <div class="flex items-center justify-between mb-2">
          ${priorityBadge}
          <div class="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity" onclick="event.stopPropagation()">
            <button onclick="LukeApp.duplicateTask('${task.id}')" class="p-1 hover:bg-slate-700 text-slate-400 hover:text-indigo-300 rounded" title="Dupliquer">
              📋
            </button>
            <button onclick="LukeApp.openEditTaskModal('${task.id}')" class="p-1 hover:bg-slate-700 text-slate-400 hover:text-white rounded" title="Modifier">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
            </button>
            <button onclick="LukeApp.confirmDeleteTask('${task.id}')" class="p-1 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 rounded" title="Supprimer">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>

        <!-- Titre -->
        <h4 class="text-sm font-semibold text-slate-100 mb-1 leading-snug line-clamp-2">${task.title}</h4>

        <!-- Description optionnelle -->
        ${task.description ? `<p class="text-xs text-slate-400 line-clamp-2 mb-2.5">${task.description}</p>` : ''}

        <!-- Tags -->
        ${tagsHtml ? `<div class="flex flex-wrap gap-1 mb-2.5">${tagsHtml}</div>` : ''}

        <!-- Indicateurs sous-tâches & commentaires -->
        ${(subtasksBadge || commentsBadge) ? `
          <div class="flex items-center space-x-3 mb-2.5 pt-1">
            ${subtasksBadge}
            ${commentsBadge}
          </div>
        ` : ''}

        <!-- Footer : Date & Assigné -->
        <div class="flex items-center justify-between pt-2 border-t border-slate-700/50 mt-2">
          ${dueDateHtml || '<span></span>'}
          ${assignee ? `
            <div class="flex items-center space-x-1.5" title="Assigné à : ${assignee.name}">
              <div class="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white shadow" style="background-color: ${assignee.avatar_color || '#4F46E5'}">
                ${this.getInitials(assignee.name)}
              </div>
              <span class="text-[11px] text-slate-400">${assignee.name.split(' ')[0]}</span>
            </div>
          ` : `
            <span class="text-[10px] text-slate-500 italic">Non assigné</span>
          `}
        </div>
      </div>
    `;
  },

  // --------------------------------------------------------------------------
  // 6. Vue Liste / Tableau (Table View Notion/ClickUp)
  // --------------------------------------------------------------------------
  renderListView() {
    const tbody = document.getElementById("list-view-tbody");
    if (!tbody) return;

    const filteredTasks = this.getFilteredTasks();

    if (filteredTasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-8 text-center text-slate-500">Aucune tâche trouvée pour ce filtre.</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filteredTasks.map(t => {
      const assignee = this.state.users.find(u => u.id === t.assignee_id);
      const isOverdue = t.due_date && new Date(t.due_date) < new Date() && t.status !== "DONE";
      const subtasks = t.subtasks || [];
      const stDone = subtasks.filter(s => s.done).length;

      return `
        <tr class="list-view-row border-b border-slate-800/60 cursor-pointer" onclick="LukeApp.openEditTaskModal('${t.id}')">
          <td class="py-3 px-4 font-semibold text-white max-w-xs truncate">
            <div>${t.title}</div>
            ${t.description ? `<div class="text-[11px] text-slate-400 truncate">${t.description}</div>` : ''}
          </td>
          <td class="py-3 px-4" onclick="event.stopPropagation()">
            <select onchange="LukeApp.quickChangeStatus('${t.id}', this.value)" class="bg-slate-800 border border-slate-700 text-[11px] font-semibold rounded-lg px-2 py-1 text-slate-200 cursor-pointer">
              <option value="TODO" ${t.status === 'TODO' ? 'selected' : ''}>À faire</option>
              <option value="IN_PROGRESS" ${t.status === 'IN_PROGRESS' ? 'selected' : ''}>En cours</option>
              <option value="IN_REVIEW" ${t.status === 'IN_REVIEW' ? 'selected' : ''}>En révision</option>
              <option value="DONE" ${t.status === 'DONE' ? 'selected' : ''}>Terminé</option>
            </select>
          </td>
          <td class="py-3 px-4">
            <span class="text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
              t.priority === 'HIGH' ? 'bg-rose-500/20 text-rose-300' :
              t.priority === 'MEDIUM' ? 'bg-amber-500/20 text-amber-300' :
              'bg-emerald-500/20 text-emerald-300'
            }">${t.priority}</span>
          </td>
          <td class="py-3 px-4">
            ${assignee ? `
              <div class="flex items-center space-x-1.5">
                <div class="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white" style="background-color: ${assignee.avatar_color || '#4F46E5'}">
                  ${this.getInitials(assignee.name)}
                </div>
                <span>${assignee.name}</span>
              </div>
            ` : `<span class="text-slate-500 italic">Non assigné</span>`}
          </td>
          <td class="py-3 px-4 text-xs ${isOverdue ? 'text-rose-400 font-bold' : 'text-slate-400'}">
            ${t.due_date ? new Date(t.due_date).toLocaleDateString("fr-FR") : '-'}
            ${isOverdue ? ' ⚠️' : ''}
          </td>
          <td class="py-3 px-4 font-mono text-[11px]">
            ${subtasks.length > 0 ? `${stDone}/${subtasks.length}` : '-'}
          </td>
          <td class="py-3 px-4 text-right" onclick="event.stopPropagation()">
            <div class="flex items-center justify-end space-x-1">
              <button onclick="LukeApp.duplicateTask('${t.id}')" class="p-1 hover:bg-slate-700 text-slate-400 hover:text-white rounded" title="Dupliquer">📋</button>
              <button onclick="LukeApp.openEditTaskModal('${t.id}')" class="p-1 hover:bg-slate-700 text-slate-400 hover:text-white rounded" title="Modifier">✏️</button>
              <button onclick="LukeApp.confirmDeleteTask('${t.id}')" class="p-1 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 rounded" title="Supprimer">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  },

  async quickChangeStatus(taskId, newStatus) {
    try {
      await this.api(`/api/tasks/${taskId}`, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus })
      });
      await this.loadTasks();
      this.showToast(`Statut mis à jour : ${this.formatStatus(newStatus)}`, "success");
    } catch (err) {}
  },

  // --------------------------------------------------------------------------
  // 7. SortableJS Drag & Drop
  // --------------------------------------------------------------------------
  initSortable() {
    this.state.sortableInstances.forEach(s => s.destroy());
    this.state.sortableInstances = [];

    const columns = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"];

    columns.forEach(status => {
      const el = document.getElementById(`column-${status}`);
      if (!el) return;

      const sortable = new Sortable(el, {
        group: "luke-kanban",
        animation: 200,
        ghostClass: "sortable-ghost",
        chosenClass: "sortable-chosen",
        dragClass: "sortable-drag",
        onEnd: async (evt) => {
          const taskId = evt.item.getAttribute("data-task-id");
          if (!taskId) return;
          const targetColEl = evt.to;
          const newStatus = targetColEl.getAttribute("data-status");
          const newIndex = evt.newIndex;

          try {
            await LukeApp.moveTask(taskId, newStatus, newIndex);
          } catch (err) {
            console.error("Échec déplacement tâche:", err);
            LukeApp.loadTasks();
          }
        }
      });
      this.state.sortableInstances.push(sortable);
    });
  },

  async moveTask(taskId, newStatus, newPosition) {
    const task = this.state.tasks.find(t => t.id === taskId);
    if (task) {
      task.status = newStatus;
      task.position = newPosition;
    }
    this.updateProjectProgress();

    await this.api(`/api/tasks/${taskId}/move`, {
      method: "PATCH",
      body: JSON.stringify({
        status: newStatus,
        position: newPosition
      })
    });

    await this.loadTasks();
    this.showToast(`Tâche déplacée dans "${this.formatStatus(newStatus)}"`, "success");
  },

  // --------------------------------------------------------------------------
  // 8. Ajout Rapide Inline (au pied des colonnes)
  // --------------------------------------------------------------------------
  showInlineAdd(status) {
    document.getElementById(`inline-btn-${status}`)?.classList.add("hidden");
    const box = document.getElementById(`inline-box-${status}`);
    if (box) {
      box.classList.remove("hidden");
      const input = document.getElementById(`inline-input-${status}`);
      if (input) {
        input.value = "";
        input.focus();
      }
    }
  },

  hideInlineAdd(status) {
    document.getElementById(`inline-box-${status}`)?.classList.add("hidden");
    document.getElementById(`inline-btn-${status}`)?.classList.remove("hidden");
  },

  async submitInlineAdd(status) {
    const input = document.getElementById(`inline-input-${status}`);
    const title = input?.value.trim();
    if (!title) {
      this.hideInlineAdd(status);
      return;
    }

    try {
      await this.api("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          project_id: this.state.currentProjectId,
          title,
          status,
          priority: "MEDIUM"
        })
      });
      this.hideInlineAdd(status);
      await this.loadTasks();
      this.showToast("Tâche ajoutée !", "success");
    } catch (err) {}
  },

  // --------------------------------------------------------------------------
  // 9. Tiroir Analytics & Métriques Projet
  // --------------------------------------------------------------------------
  toggleAnalyticsDrawer() {
    this.state.analyticsOpen = !this.state.analyticsOpen;
    const drawer = document.getElementById("analytics-drawer");
    if (drawer) {
      drawer.classList.toggle("hidden", !this.state.analyticsOpen);
    }
    if (this.state.analyticsOpen) {
      this.loadProjectStats();
    }
  },

  async loadProjectStats() {
    if (!this.state.currentProjectId) return;
    try {
      const stats = await this.api(`/api/projects/${this.state.currentProjectId}/stats`);
      
      document.getElementById("stats-total").textContent = stats.total_tasks;
      document.getElementById("stats-active").textContent = (stats.status_counts.IN_PROGRESS || 0) + (stats.status_counts.IN_REVIEW || 0);
      document.getElementById("stats-done").textContent = `${stats.done_tasks} (${stats.completion_rate}%)`;
      document.getElementById("stats-overdue").textContent = stats.overdue_tasks;

      const workloadEl = document.getElementById("analytics-workload-bars");
      if (workloadEl) {
        workloadEl.innerHTML = stats.workload.map(w => `
          <div class="flex items-center justify-between space-x-3 text-xs">
            <div class="flex items-center space-x-2 w-36 truncate">
              <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${w.avatar_color}"></span>
              <span class="truncate">${w.name}</span>
            </div>
            <div class="flex-1 bg-slate-800 h-2 rounded-full overflow-hidden">
              <div class="h-full bg-indigo-500" style="width: ${stats.total_tasks > 0 ? (w.total_tasks / stats.total_tasks * 100) : 0}%"></div>
            </div>
            <span class="font-mono text-slate-400 text-[11px] w-16 text-right">${w.total_tasks} tâche(s)</span>
          </div>
        `).join("");
      }
    } catch (err) {
      console.error("Erreur calcul stats:", err);
    }
  },

  // --------------------------------------------------------------------------
  // 10. Export de Données (CSV / JSON)
  // --------------------------------------------------------------------------
  toggleExportDropdown() {
    const menu = document.getElementById("export-dropdown-menu");
    menu?.classList.toggle("hidden");
  },

  async exportProject(format) {
    document.getElementById("export-dropdown-menu")?.classList.add("hidden");
    if (!this.state.currentProjectId) return;

    try {
      const res = await this.api(`/api/projects/${this.state.currentProjectId}/export?format=${format}`);
      if (res.isBlob) {
        const url = window.URL.createObjectURL(res.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = res.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        this.showToast(`Export ${format.toUpperCase()} téléchargé avec succès !`, "success");
      }
    } catch (err) {
      this.showToast("Erreur lors de l'export des données.", "error");
    }
  },

  // --------------------------------------------------------------------------
  // 11. Filtres interactifs par Tag & Recherche
  // --------------------------------------------------------------------------
  filterByTag(tag) {
    this.state.filters.tag = tag;
    const badge = document.getElementById("active-tag-filter");
    const nameEl = document.getElementById("active-tag-name");
    if (badge && nameEl) {
      nameEl.textContent = `Tag: ${tag}`;
      badge.classList.remove("hidden");
      badge.classList.add("inline-flex");
    }
    this.filterTasks();
  },

  clearTagFilter() {
    this.state.filters.tag = "";
    const badge = document.getElementById("active-tag-filter");
    if (badge) {
      badge.classList.add("hidden");
      badge.classList.remove("inline-flex");
    }
    this.filterTasks();
  },

  toggleMyTasksFilter() {
    this.state.filters.onlyMine = !this.state.filters.onlyMine;
    const btn = document.getElementById("btn-my-tasks");
    if (btn) {
      if (this.state.filters.onlyMine) {
        btn.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white shadow-md shadow-indigo-600/30 transition flex items-center space-x-1.5";
      } else {
        btn.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center space-x-1.5";
      }
    }
    this.filterTasks();
  },

  onFilterChange() {
    this.state.filters.assigneeId = document.getElementById("filter-assignee").value;
    this.state.filters.priority = document.getElementById("filter-priority").value;
    this.filterTasks();
  },

  resetFilters() {
    this.state.filters.search = "";
    this.state.filters.assigneeId = "";
    this.state.filters.priority = "";
    this.state.filters.tag = "";
    this.state.filters.onlyMine = false;

    const sInput = document.getElementById("search-input");
    const aSelect = document.getElementById("filter-assignee");
    const pSelect = document.getElementById("filter-priority");
    const myBtn = document.getElementById("btn-my-tasks");

    if (sInput) sInput.value = "";
    if (aSelect) aSelect.value = "";
    if (pSelect) pSelect.value = "";
    if (myBtn) myBtn.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center space-x-1.5";

    this.clearTagFilter();
    this.filterTasks();
  },

  filterTasks() {
    this.renderKanban();
    this.renderListView();
  },

  // --------------------------------------------------------------------------
  // 12. Modale Tâche Complète (Checklist / Sous-tâches & Commentaires)
  // --------------------------------------------------------------------------
  openNewTaskModal(defaultStatus = "TODO") {
    if (!this.state.currentProjectId) {
      this.showToast("Veuillez d'abord créer ou sélectionner un projet.", "warning");
      return;
    }
    this.state.currentEditingTaskId = null;
    this.state.currentEditingTask = null;

    document.getElementById("task-modal-title").textContent = "Créer une nouvelle tâche";
    document.getElementById("task-form").reset();
    document.getElementById("task-id-input").value = "";
    document.getElementById("task-status-input").value = defaultStatus;
    
    // Cacher sections sous-tâches et commentaires lors de la création
    document.getElementById("subtasks-section")?.classList.add("hidden");
    document.getElementById("comments-section")?.classList.add("hidden");
    document.getElementById("task-duplicate-btn")?.classList.add("hidden");
    document.getElementById("task-delete-btn")?.classList.add("hidden");

    const assigneeSelect = document.getElementById("task-assignee-input");
    assigneeSelect.innerHTML = `<option value="">Non assigné</option>` +
      this.state.users.map(u => `<option value="${u.id}">${u.name} (${u.role})</option>`).join("");

    this.openModal("task-modal");
  },

  openEditTaskModal(taskId) {
    const task = this.state.tasks.find(t => t.id === taskId);
    if (!task) return;

    this.state.currentEditingTaskId = taskId;
    this.state.currentEditingTask = task;

    document.getElementById("task-modal-title").textContent = "Détails & Édition de la tâche";
    document.getElementById("task-id-input").value = task.id;
    document.getElementById("task-title-input").value = task.title;
    document.getElementById("task-desc-input").value = task.description || "";
    document.getElementById("task-status-input").value = task.status;
    document.getElementById("task-priority-input").value = task.priority;
    document.getElementById("task-tags-input").value = (task.tags || []).join(", ");
    
    if (task.due_date) {
      document.getElementById("task-due-date-input").value = task.due_date.substring(0, 10);
    } else {
      document.getElementById("task-due-date-input").value = "";
    }

    const assigneeSelect = document.getElementById("task-assignee-input");
    assigneeSelect.innerHTML = `<option value="">Non assigné</option>` +
      this.state.users.map(u => `<option value="${u.id}" ${u.id === task.assignee_id ? 'selected' : ''}>${u.name} (${u.role})</option>`).join("");

    // Afficher sous-tâches, commentaires et boutons d'action
    document.getElementById("subtasks-section")?.classList.remove("hidden");
    document.getElementById("comments-section")?.classList.remove("hidden");
    document.getElementById("task-duplicate-btn")?.classList.remove("hidden");
    document.getElementById("task-delete-btn")?.classList.remove("hidden");

    this.renderModalSubtasks();
    this.renderModalComments();

    this.openModal("task-modal");
  },

  renderModalSubtasks() {
    const task = this.state.currentEditingTask;
    if (!task) return;

    const listEl = document.getElementById("subtasks-list");
    const badgeEl = document.getElementById("subtasks-progress-badge");
    const barEl = document.getElementById("subtasks-progress-bar");

    const subtasks = task.subtasks || [];
    const doneCount = subtasks.filter(s => s.done).length;
    const pct = subtasks.length > 0 ? Math.round((doneCount / subtasks.length) * 100) : 0;

    if (badgeEl) badgeEl.textContent = `${doneCount}/${subtasks.length} complétées`;
    if (barEl) barEl.style.width = `${pct}%`;

    if (listEl) {
      if (subtasks.length === 0) {
        listEl.innerHTML = `<p class="text-[11px] text-slate-500 italic">Aucune sous-tâche définie.</p>`;
      } else {
        listEl.innerHTML = subtasks.map(st => `
          <div class="flex items-center justify-between p-1.5 rounded-lg hover:bg-slate-800/80 transition group">
            <label class="flex items-center space-x-2.5 cursor-pointer flex-1">
              <input type="checkbox" ${st.done ? 'checked' : ''} onchange="LukeApp.toggleSubtask('${st.id}')" class="checklist-checkbox">
              <span class="checklist-text text-xs ${st.done ? 'checked' : 'text-slate-200'}">${st.title}</span>
            </label>
            <button type="button" onclick="LukeApp.deleteSubtask('${st.id}')" class="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 text-xs px-1.5 transition">
              &times;
            </button>
          </div>
        `).join("");
      }
    }
  },

  async addNewSubtask() {
    const input = document.getElementById("new-subtask-input");
    const title = input?.value.trim();
    if (!title || !this.state.currentEditingTaskId) return;

    try {
      const updated = await this.api(`/api/tasks/${this.state.currentEditingTaskId}/subtasks`, {
        method: "POST",
        body: JSON.stringify({ title })
      });
      input.value = "";
      this.state.currentEditingTask = updated;
      this.renderModalSubtasks();
      await this.loadTasks();
    } catch (err) {}
  },

  async toggleSubtask(subtaskId) {
    if (!this.state.currentEditingTaskId) return;
    try {
      const updated = await this.api(`/api/tasks/${this.state.currentEditingTaskId}/subtasks/${subtaskId}`, {
        method: "PATCH",
        body: JSON.stringify({})
      });
      this.state.currentEditingTask = updated;
      this.renderModalSubtasks();
      await this.loadTasks();
    } catch (err) {}
  },

  async deleteSubtask(subtaskId) {
    if (!this.state.currentEditingTaskId) return;
    try {
      const updated = await this.api(`/api/tasks/${this.state.currentEditingTaskId}/subtasks/${subtaskId}`, {
        method: "DELETE"
      });
      this.state.currentEditingTask = updated;
      this.renderModalSubtasks();
      await this.loadTasks();
    } catch (err) {}
  },

  renderModalComments() {
    const task = this.state.currentEditingTask;
    if (!task) return;

    const timeline = document.getElementById("comments-timeline");
    if (!timeline) return;

    const comments = task.comments || [];
    if (comments.length === 0) {
      timeline.innerHTML = `<p class="text-[11px] text-slate-500 italic">Aucun commentaire pour le moment.</p>`;
      return;
    }

    timeline.innerHTML = comments.map(c => `
      <div class="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 text-xs flex items-start space-x-2.5">
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0 shadow" style="background-color: ${c.user_avatar_color || '#4F46E5'}">
          ${this.getInitials(c.user_name)}
        </div>
        <div class="flex-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-slate-200 text-[11px]">${c.user_name}</span>
            <div class="flex items-center space-x-1 text-[10px] text-slate-500">
              <span>${new Date(c.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
              <button type="button" onclick="LukeApp.deleteComment('${c.id}')" class="hover:text-rose-400 ml-1">&times;</button>
            </div>
          </div>
          <p class="text-slate-300 mt-1 leading-relaxed">${c.content}</p>
        </div>
      </div>
    `).join("");
  },

  async submitComment() {
    const input = document.getElementById("new-comment-input");
    const content = input?.value.trim();
    if (!content || !this.state.currentEditingTaskId) return;

    try {
      const updated = await this.api(`/api/tasks/${this.state.currentEditingTaskId}/comments`, {
        method: "POST",
        body: JSON.stringify({ content })
      });
      input.value = "";
      this.state.currentEditingTask = updated;
      this.renderModalComments();
      await this.loadTasks();
      this.showToast("Commentaire publié !", "success");
    } catch (err) {}
  },

  async deleteComment(commentId) {
    if (!this.state.currentEditingTaskId) return;
    try {
      const updated = await this.api(`/api/tasks/${this.state.currentEditingTaskId}/comments/${commentId}`, {
        method: "DELETE"
      });
      this.state.currentEditingTask = updated;
      this.renderModalComments();
      await this.loadTasks();
    } catch (err) {}
  },

  async duplicateTask(taskId) {
    try {
      const created = await this.api(`/api/tasks/${taskId}/duplicate`, { method: "POST" });
      await this.loadTasks();
      this.showToast(`Tâche dupliquée : "${created.title}"`, "success");
    } catch (err) {}
  },

  async duplicateCurrentTask() {
    if (!this.state.currentEditingTaskId) return;
    const tid = this.state.currentEditingTaskId;
    this.closeModal("task-modal");
    await this.duplicateTask(tid);
  },

  deleteCurrentTaskFromModal() {
    if (!this.state.currentEditingTaskId) return;
    const tid = this.state.currentEditingTaskId;
    this.closeModal("task-modal");
    this.confirmDeleteTask(tid);
  },

  async handleTaskFormSubmit(evt) {
    evt.preventDefault();
    const taskId = document.getElementById("task-id-input").value;
    const title = document.getElementById("task-title-input").value;
    const description = document.getElementById("task-desc-input").value;
    const status = document.getElementById("task-status-input").value;
    const priority = document.getElementById("task-priority-input").value;
    const tagsRaw = document.getElementById("task-tags-input").value;
    const dueDateRaw = document.getElementById("task-due-date-input").value;
    const assigneeId = document.getElementById("task-assignee-input").value || null;

    const tags = tagsRaw.split(",").map(t => t.trim()).filter(Boolean);
    const dueDate = dueDateRaw ? `${dueDateRaw}T18:00:00Z` : null;

    try {
      if (taskId) {
        await this.api(`/api/tasks/${taskId}`, {
          method: "PUT",
          body: JSON.stringify({
            title,
            description,
            status,
            priority,
            tags,
            due_date: dueDate,
            assignee_id: assigneeId
          })
        });
        this.showToast("Tâche mise à jour avec succès !", "success");
      } else {
        await this.api("/api/tasks", {
          method: "POST",
          body: JSON.stringify({
            project_id: this.state.currentProjectId,
            title,
            description,
            status,
            priority,
            tags,
            due_date: dueDate,
            assignee_id: assigneeId
          })
        });
        this.showToast("Tâche créée avec succès !", "success");
      }
      this.closeModal("task-modal");
      await this.loadTasks();
    } catch (err) {}
  },

  confirmDeleteTask(taskId) {
    const task = this.state.tasks.find(t => t.id === taskId);
    if (!task) return;

    this.openConfirmModal({
      title: "Supprimer la tâche",
      message: `Êtes-vous sûr de vouloir supprimer définitivement la tâche <strong>"${task.title}"</strong> ?`,
      dangerText: "Supprimer définitivement",
      onConfirm: async () => {
        await this.api(`/api/tasks/${taskId}`, { method: "DELETE" });
        this.showToast("Tâche supprimée avec succès.", "success");
        await this.loadTasks();
      }
    });
  },

  // --------------------------------------------------------------------------
  // 13. Projets (Modale & CRUD)
  // --------------------------------------------------------------------------
  openNewProjectModal() {
    document.getElementById("project-modal-title").textContent = "Nouveau Projet";
    document.getElementById("project-form").reset();
    document.getElementById("project-id-input").value = "";
    this.renderProjectMembersCheckboxes([]);
    this.openModal("project-modal");
  },

  openEditProjectModal(projectId) {
    const proj = this.state.projects.find(p => p.id === projectId);
    if (!proj) return;

    document.getElementById("project-modal-title").textContent = "Modifier le Projet";
    document.getElementById("project-id-input").value = proj.id;
    document.getElementById("project-name-input").value = proj.name;
    document.getElementById("project-desc-input").value = proj.description || "";
    document.getElementById("project-status-input").value = proj.status || "ACTIVE";
    this.renderProjectMembersCheckboxes(proj.member_ids || []);
    this.openModal("project-modal");
  },

  renderProjectMembersCheckboxes(selectedIds = []) {
    const container = document.getElementById("project-members-checkboxes");
    if (!container) return;

    container.innerHTML = this.state.users.map(u => `
      <label class="flex items-center space-x-2.5 p-2 rounded-lg hover:bg-slate-800 cursor-pointer border border-slate-800 transition">
        <input type="checkbox" name="project_member" value="${u.id}" ${selectedIds.includes(u.id) ? 'checked' : ''} class="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-900">
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white shadow" style="background-color: ${u.avatar_color || '#4F46E5'}">
          ${this.getInitials(u.name)}
        </div>
        <span class="text-xs text-slate-200">${u.name} <span class="text-[10px] text-slate-400">(${u.role})</span></span>
      </label>
    `).join("");
  },

  async handleProjectFormSubmit(evt) {
    evt.preventDefault();
    const projectId = document.getElementById("project-id-input").value;
    const name = document.getElementById("project-name-input").value;
    const description = document.getElementById("project-desc-input").value;
    const status = document.getElementById("project-status-input").value;

    const memberCheckboxes = document.querySelectorAll("input[name='project_member']:checked");
    const member_ids = Array.from(memberCheckboxes).map(cb => cb.value);

    try {
      if (projectId) {
        await this.api(`/api/projects/${projectId}`, {
          method: "PUT",
          body: JSON.stringify({ name, description, status, member_ids })
        });
        this.showToast("Projet mis à jour avec succès !", "success");
      } else {
        const created = await this.api("/api/projects", {
          method: "POST",
          body: JSON.stringify({ name, description, status, member_ids })
        });
        this.state.currentProjectId = created.id;
        this.showToast("Projet créé avec succès !", "success");
      }
      this.closeModal("project-modal");
      await this.loadProjects();
    } catch (err) {}
  },

  confirmDeleteProject(projectId) {
    const proj = this.state.projects.find(p => p.id === projectId);
    if (!proj) return;

    this.openConfirmModal({
      title: "Supprimer le projet",
      message: `Attention : La suppression du projet <strong>"${proj.name}"</strong> entraînera la <strong>suppression en cascade de toutes ses tâches</strong> associées.`,
      dangerText: "Supprimer le projet et ses tâches",
      onConfirm: async () => {
        await this.api(`/api/projects/${projectId}`, { method: "DELETE" });
        this.showToast("Projet et tâches supprimés.", "success");
        this.state.currentProjectId = null;
        await this.loadProjects();
      }
    });
  },

  // --------------------------------------------------------------------------
  // 14. Utilisateurs (Modale & CRUD)
  // --------------------------------------------------------------------------
  openNewUserModal() {
    document.getElementById("user-modal-title").textContent = "Nouveau Collaborateur";
    document.getElementById("user-form").reset();
    document.getElementById("user-id-input").value = "";
    document.getElementById("user-color-input").value = "#4F46E5";
    this.openModal("user-modal");
  },

  openEditUserModal(userId) {
    const u = this.state.users.find(x => x.id === userId);
    if (!u) return;

    document.getElementById("user-modal-title").textContent = "Modifier le Collaborateur";
    document.getElementById("user-id-input").value = u.id;
    document.getElementById("user-name-input").value = u.name;
    document.getElementById("user-email-input").value = u.email;
    document.getElementById("user-role-input").value = u.role;
    document.getElementById("user-color-input").value = u.avatar_color || "#4F46E5";
    this.openModal("user-modal");
  },

  async handleUserFormSubmit(evt) {
    evt.preventDefault();
    const userId = document.getElementById("user-id-input").value;
    const name = document.getElementById("user-name-input").value;
    const email = document.getElementById("user-email-input").value;
    const role = document.getElementById("user-role-input").value;
    const avatar_color = document.getElementById("user-color-input").value;

    try {
      if (userId) {
        await this.api(`/api/users/${userId}`, {
          method: "PUT",
          body: JSON.stringify({ name, email, role, avatar_color })
        });
        this.showToast("Collaborateur mis à jour !", "success");
      } else {
        await this.api("/api/users", {
          method: "POST",
          body: JSON.stringify({ name, email, role, avatar_color })
        });
        this.showToast("Collaborateur ajouté avec succès !", "success");
      }
      this.closeModal("user-modal");
      await this.loadUsers();
    } catch (err) {}
  },

  confirmDeleteUser(userId) {
    const u = this.state.users.find(x => x.id === userId);
    if (!u) return;

    this.openConfirmModal({
      title: "Supprimer le collaborateur",
      message: `La suppression de <strong>"${u.name}"</strong> le retirera de tous les projets de l'entreprise et désassignera ses tâches en cours.`,
      dangerText: "Supprimer le collaborateur",
      onConfirm: async () => {
        await this.api(`/api/users/${userId}`, { method: "DELETE" });
        this.showToast("Collaborateur supprimé et tâches désassignées.", "success");
        await this.loadUsers();
        await this.loadTasks();
      }
    });
  },

  // --------------------------------------------------------------------------
  // 15. Entreprises (Modale & CRUD)
  // --------------------------------------------------------------------------
  openNewCompanyModal() {
    document.getElementById("company-modal-title").textContent = "Nouvelle Entreprise";
    document.getElementById("company-form").reset();
    document.getElementById("company-id-input").value = "";
    this.openModal("company-modal");
  },

  openEditCurrentCompanyModal() {
    const comp = this.state.currentCompany;
    if (!comp) return;

    document.getElementById("company-modal-title").textContent = "Paramètres de l'Entreprise";
    document.getElementById("company-id-input").value = comp.id;
    document.getElementById("company-name-input").value = comp.name;
    document.getElementById("company-slug-input").value = comp.slug || "";
    document.getElementById("company-plan-input").value = comp.plan || "PRO";
    this.openModal("company-modal");
  },

  async handleCompanyFormSubmit(evt) {
    evt.preventDefault();
    const companyId = document.getElementById("company-id-input").value;
    const name = document.getElementById("company-name-input").value;
    const slug = document.getElementById("company-slug-input").value;
    const plan = document.getElementById("company-plan-input").value;

    try {
      if (companyId) {
        const updated = await this.api(`/api/companies/${companyId}`, {
          method: "PUT",
          body: JSON.stringify({ name, slug, plan })
        });
        this.showToast("Entreprise mise à jour avec succès !", "success");
        await this.loadCompanies(updated.id);
      } else {
        const created = await this.api("/api/companies", {
          method: "POST",
          body: JSON.stringify({ name, slug: slug || undefined, plan })
        });
        this.showToast("Nouvelle entreprise créée avec succès !", "success");
        await this.loadCompanies(created.id);
      }
      this.closeModal("company-modal");
    } catch (err) {}
  },

  confirmDeleteCurrentCompany() {
    const comp = this.state.currentCompany;
    if (!comp) return;

    this.openConfirmModal({
      title: "Supprimer définitivement l'organisation",
      message: `<strong>ATTENTION SUPPRESSION EN CASCADE :</strong><br>La suppression de l'entreprise <strong>"${comp.name}"</strong> détruira irréversiblement <strong>TOUS ses projets, TOUS ses utilisateurs et TOUTES ses tâches</strong> en base de données.`,
      dangerText: "Tout supprimer en cascade",
      onConfirm: async () => {
        await this.api(`/api/companies/${comp.id}`, { method: "DELETE" });
        this.showToast(`Entreprise "${comp.name}" supprimée en cascade.`, "success");
        this.state.currentCompanyId = null;
        await this.loadCompanies();
      }
    });
  },

  // --------------------------------------------------------------------------
  // 16. Onglets & Navigation
  // --------------------------------------------------------------------------
  switchTab(tabName) {
    this.state.activeTab = tabName;
    const tabs = ["kanban", "list", "projects", "team", "architecture"];

    tabs.forEach(t => {
      const el = document.getElementById(`tab-content-${t}`);
      const btn = document.getElementById(`tab-btn-${t}`);
      if (el) el.classList.toggle("hidden", t !== tabName);
      if (btn) {
        if (t === tabName) {
          btn.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white shadow-sm";
        } else {
          btn.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition";
        }
      }
    });

    if (tabName === "projects") this.renderProjectsTab();
    if (tabName === "team") this.renderTeamTab();
    if (tabName === "architecture") this.renderArchitectureTab();
    if (tabName === "kanban") this.renderKanban();
    if (tabName === "list") this.renderListView();
  },

  renderProjectsTab() {
    const container = document.getElementById("projects-tab-list");
    if (!container) return;

    if (this.state.projects.length === 0) {
      container.innerHTML = `
        <div class="col-span-2 text-center py-12 text-slate-500">
          <p class="text-sm">Aucun projet dans cette entreprise.</p>
          <button onclick="LukeApp.openNewProjectModal()" class="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold">Créer un premier projet</button>
        </div>
      `;
      return;
    }

    container.innerHTML = this.state.projects.map(p => `
      <div class="glass-panel border border-slate-700/80 rounded-2xl p-5 hover:border-indigo-500/50 transition shadow-lg">
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center space-x-2">
              <h3 class="text-base font-bold text-slate-100">${p.name}</h3>
              <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full ${p.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-700 text-slate-400'}">${p.status}</span>
            </div>
            <p class="text-xs text-slate-400 mt-1 max-w-xl">${p.description || 'Aucune description'}</p>
          </div>
          <div class="flex items-center space-x-2">
            <button onclick="LukeApp.setProject('${p.id}'); LukeApp.switchTab('kanban');" class="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 text-xs font-semibold rounded-lg border border-indigo-500/30 transition">
              Ouvrir Kanban
            </button>
            <button onclick="LukeApp.openEditProjectModal('${p.id}')" class="p-1.5 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg" title="Modifier">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
            </button>
            <button onclick="LukeApp.confirmDeleteProject('${p.id}')" class="p-1.5 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 rounded-lg" title="Supprimer">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </div>

        <div class="mt-4 pt-4 border-t border-slate-700/60 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-xs text-slate-400">Équipe :</span>
            <div class="flex items-center">
              ${(p.members || []).map(m => `
                <div class="w-6 h-6 -ml-1 first:ml-0 rounded-full flex items-center justify-center text-[9px] font-bold text-white border-2 border-slate-800" style="background-color: ${m.avatar_color || '#4F46E5'}" title="${m.name}">
                  ${this.getInitials(m.name)}
                </div>
              `).join("") || `<span class="text-xs text-slate-500 italic">Aucun</span>`}
            </div>
          </div>
          <div class="flex items-center space-x-3 text-xs">
            <span class="text-slate-400">${p.done_tasks || 0} / ${p.total_tasks || 0} terminées</span>
            <div class="w-24 bg-slate-700 h-2 rounded-full overflow-hidden">
              <div class="bg-indigo-500 h-full rounded-full" style="width: ${p.progress_percentage || 0}%"></div>
            </div>
            <span class="font-bold text-indigo-400">${p.progress_percentage || 0}%</span>
          </div>
        </div>
      </div>
    `).join("");
  },

  renderTeamTab() {
    const container = document.getElementById("team-tab-list");
    if (!container) return;

    container.innerHTML = this.state.users.map(u => `
      <div class="glass-panel border border-slate-700/80 rounded-2xl p-4 flex items-center justify-between hover:border-slate-600 transition shadow">
        <div class="flex items-center space-x-3.5">
          <div class="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-lg" style="background-color: ${u.avatar_color || '#4F46E5'}">
            ${this.getInitials(u.name)}
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h4 class="text-sm font-bold text-slate-100">${u.name}</h4>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${u.role === 'ADMIN' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'}">${u.role}</span>
            </div>
            <p class="text-xs text-slate-400 font-mono mt-0.5">${u.email}</p>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="LukeApp.setUser('${u.id}')" class="px-2.5 py-1 text-xs rounded-lg ${u.id === this.state.currentUserId ? 'bg-indigo-600 text-white font-semibold' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'} transition">
            ${u.id === this.state.currentUserId ? 'Actif' : 'Endosser ce rôle'}
          </button>
          <button onclick="LukeApp.openEditUserModal('${u.id}')" class="p-1.5 hover:bg-slate-700 text-slate-400 hover:text-white rounded-lg">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
          </button>
          <button onclick="LukeApp.confirmDeleteUser('${u.id}')" class="p-1.5 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 rounded-lg">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </div>
      </div>
    `).join("");
  },

  renderArchitectureTab() {
    const comp = this.state.currentCompany;
    if (!comp) return;

    const cidEl = document.getElementById("arch-current-cid");
    const countUsersEl = document.getElementById("arch-count-users");
    const countProjEl = document.getElementById("arch-count-projects");
    const countTasksEl = document.getElementById("arch-count-tasks");

    if (cidEl) cidEl.textContent = comp.id;
    if (countUsersEl) countUsersEl.textContent = this.state.users.length;
    if (countProjEl) countProjEl.textContent = this.state.projects.length;
    if (countTasksEl) countTasksEl.textContent = this.state.tasks.length;
  },

  // --------------------------------------------------------------------------
  // 17. Webhook Discord Test
  // --------------------------------------------------------------------------
  async testDiscordWebhook() {
    const btn = document.getElementById("btn-test-discord");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `⏳ Envoi...`;
    }

    try {
      const res = await this.api("/api/webhook/test", {
        method: "POST",
        body: JSON.stringify({
          message: `Notification de test émise depuis l'entreprise **${this.state.currentCompany?.name || 'Luke'}** !`
        })
      });
      this.showToast(res.message, res.status === "success" ? "success" : "warning");
    } catch (err) {
      this.showToast("Erreur lors de l'appel au webhook Discord.", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `🔔 <span class="hidden xl:inline">Test Webhook</span>`;
      }
    }
  },

  // --------------------------------------------------------------------------
  // 18. Raccourcis Clavier & Helpers UI
  // --------------------------------------------------------------------------
  setupKeyboardShortcuts() {
    window.addEventListener("keydown", (e) => {
      const activeTagName = document.activeElement?.tagName?.toLowerCase();
      const isInput = activeTagName === "input" || activeTagName === "textarea" || activeTagName === "select";

      if (e.key === "Escape") {
        this.closeAllModals();
        return;
      }

      if (!isInput) {
        if (e.key === "n" || e.key === "N") {
          e.preventDefault();
          this.openNewTaskModal();
        } else if (e.key === "f" || e.key === "F" || e.key === "/") {
          e.preventDefault();
          document.getElementById("search-input")?.focus();
        } else if (e.key === "?") {
          e.preventDefault();
          this.openShortcutsModal();
        }
      }
    });
  },

  openShortcutsModal() {
    this.openModal("shortcuts-modal");
  },

  closeAllModals() {
    const modals = ["task-modal", "project-modal", "user-modal", "company-modal", "shortcuts-modal", "confirm-modal"];
    modals.forEach(m => this.closeModal(m));
    document.getElementById("companies-dropdown-menu")?.classList.add("hidden");
    document.getElementById("users-dropdown-menu")?.classList.add("hidden");
    document.getElementById("export-dropdown-menu")?.classList.add("hidden");
  },

  getInitials(name) {
    if (!name) return "??";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  },

  formatStatus(status) {
    switch (status) {
      case "TODO": return "À faire";
      case "IN_PROGRESS": return "En cours";
      case "IN_REVIEW": return "En révision";
      case "DONE": return "Terminé";
      default: return status;
    }
  },

  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove("hidden");
      modal.classList.add("flex");
    }
  },

  closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }
  },

  openConfirmModal({ title, message, dangerText, onConfirm }) {
    document.getElementById("confirm-modal-title").textContent = title;
    document.getElementById("confirm-modal-message").innerHTML = message;
    
    const confirmBtn = document.getElementById("confirm-modal-btn");
    confirmBtn.textContent = dangerText || "Confirmer la suppression";
    
    const newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

    newBtn.addEventListener("click", async () => {
      this.closeModal("confirm-modal");
      if (onConfirm) await onConfirm();
    });

    this.openModal("confirm-modal");
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    let bg = "bg-slate-800 border-slate-700 text-slate-100";
    let icon = "ℹ️";

    if (type === "success") {
      bg = "bg-emerald-950/90 border-emerald-500/50 text-emerald-200";
      icon = "✅";
    } else if (type === "error") {
      bg = "bg-rose-950/90 border-rose-500/50 text-rose-200";
      icon = "⚠️";
    } else if (type === "warning") {
      bg = "bg-amber-950/90 border-amber-500/50 text-amber-200";
      icon = "⚡";
    }

    toast.className = `flex items-center space-x-2.5 px-4 py-3 rounded-xl border shadow-xl text-xs font-medium transition-all duration-300 transform translate-y-2 opacity-0 toast-slide-in ${bg}`;
    toast.innerHTML = `<span>${icon}</span><span class="flex-1">${message}</span>`;

    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    });

    setTimeout(() => {
      toast.classList.add("opacity-0", "translate-y-2");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  renderNoCompanyState() {
    document.getElementById("main-app-content").innerHTML = `
      <div class="max-w-md mx-auto text-center py-20">
        <h2 class="text-xl font-bold text-slate-200">Bienvenue sur Luke SaaS</h2>
        <p class="text-sm text-slate-400 mt-2">Aucune entreprise n'existe actuellement. Créez votre première organisation pour démarrer.</p>
        <button onclick="LukeApp.openNewCompanyModal()" class="mt-6 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-sm shadow-lg shadow-indigo-600/30">
          + Créer une entreprise
        </button>
      </div>
    `;
  },

  renderNoProjectState() {
    const columns = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"];
    columns.forEach(col => {
      const el = document.getElementById(`column-${col}`);
      if (el) el.innerHTML = "";
    });
    const titleEl = document.getElementById("project-title-display");
    const descEl = document.getElementById("project-desc-display");
    if (titleEl) titleEl.textContent = "Aucun projet actif";
    if (descEl) descEl.textContent = "Créez un projet pour ce workspace afin de visualiser les colonnes Kanban.";
    this.updateProjectProgress();
  },

  setupEventListeners() {
    const compBtn = document.getElementById("header-company-btn");
    const compMenu = document.getElementById("companies-dropdown-menu");
    if (compBtn && compMenu) {
      compBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        compMenu.classList.toggle("hidden");
        document.getElementById("users-dropdown-menu")?.classList.add("hidden");
        document.getElementById("export-dropdown-menu")?.classList.add("hidden");
      });
    }

    const userBtn = document.getElementById("header-user-btn");
    const userMenu = document.getElementById("users-dropdown-menu");
    if (userBtn && userMenu) {
      userBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        userMenu.classList.toggle("hidden");
        document.getElementById("companies-dropdown-menu")?.classList.add("hidden");
        document.getElementById("export-dropdown-menu")?.classList.add("hidden");
      });
    }

    document.addEventListener("click", () => {
      compMenu?.classList.add("hidden");
      userMenu?.classList.add("hidden");
      document.getElementById("export-dropdown-menu")?.classList.add("hidden");
    });

    document.getElementById("task-form")?.addEventListener("submit", (e) => this.handleTaskFormSubmit(e));
    document.getElementById("project-form")?.addEventListener("submit", (e) => this.handleProjectFormSubmit(e));
    document.getElementById("user-form")?.addEventListener("submit", (e) => this.handleUserFormSubmit(e));
    document.getElementById("company-form")?.addEventListener("submit", (e) => this.handleCompanyFormSubmit(e));

    document.getElementById("search-input")?.addEventListener("input", (e) => {
      this.state.filters.search = e.target.value;
      this.filterTasks();
    });
  }
};

window.LukeApp = LukeApp;
document.addEventListener("DOMContentLoaded", () => LukeApp.init());
