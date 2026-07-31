/**
 * Career Tracker — Dashboard JavaScript
 *
 * Handles:
 * - Server-Sent Events (SSE) for live job notifications
 * - Toast popup notifications
 * - Sidebar toggle for mobile
 * - Global search
 * - Unread badge updates
 */

(function () {
    "use strict";

    // ─── DOM References ──────────────────────────────
    const toastContainer = document.getElementById("toast-container");
    const notifFeed = document.getElementById("notification-feed");
    const sidebar = document.getElementById("sidebar");
    const menuToggle = document.getElementById("menu-toggle");
    const unreadBadge = document.getElementById("unread-badge");
    const bellBadge = document.getElementById("bell-badge");
    const globalSearch = document.getElementById("global-search");

    let unreadCount = 0;

    // ─── SSE Connection & Auto Refresh ───────────────
    function connectSSE() {
        if (typeof EventSource === "undefined") {
            console.warn("SSE not supported in this browser.");
            return;
        }

        const evtSource = new EventSource("/stream");

        evtSource.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);

                if (data.type === "connected") {
                    console.log("🟢 Connected to live notification stream.");
                    return;
                }

                // New job notification received
                handleNewNotification(data);
            } catch (e) {
                console.warn("SSE parse error:", e);
            }
        };

        evtSource.onerror = function () {
            console.warn("SSE connection lost. Reconnecting in 5s...");
            evtSource.close();
            setTimeout(connectSSE, 5000);
        };

        // Periodic auto-refresh every 60s for stats & notifications
        setInterval(function() {
            fetchStats();
        }, 60000);
    }

    // ─── Handle New Notification ─────────────────────
    function handleNewNotification(data) {
        // Show toast popup
        showToast(data);

        // Prepend to notification feed (if on dashboard/notifications page)
        if (notifFeed) {
            const card = createNotificationCard(data);
            notifFeed.insertBefore(card, notifFeed.firstChild);

            // Remove empty state if present
            const emptyState = notifFeed.querySelector(".empty-state");
            if (emptyState) emptyState.remove();
        }

        // Update unread count
        unreadCount++;
        updateBadges();

        // Play subtle notification sound (optional)
        playNotificationSound(data.priority);
    }

    // ─── Toast Popup ─────────────────────────────────
    function showToast(data) {
        if (!toastContainer) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${data.priority || "normal"}`;

        const priorityEmoji = {
            urgent: "🔴",
            hot: "🟢",
            good: "🔵",
            worth_checking: "🟡",
            new: "🟣",
            normal: "⚪",
        };

        toast.innerHTML = `
            <div class="toast-title">
                ${priorityEmoji[data.priority] || "📋"} ${escapeHtml(data.title || "New Job")}
            </div>
            <div class="toast-body">
                ${escapeHtml(data.company || "")}
                ${data.location ? " · " + escapeHtml(data.location) : ""}
                ${data.match_score ? " · " + Math.round(data.match_score * 100) + "% match" : ""}
            </div>
        `;

        // Click to dismiss
        toast.addEventListener("click", () => {
            toast.style.animation = "toastOut 0.3s ease forwards";
            setTimeout(() => toast.remove(), 300);
        });

        toastContainer.appendChild(toast);

        // Auto-dismiss after 8 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.animation = "toastOut 0.3s ease forwards";
                setTimeout(() => toast.remove(), 300);
            }
        }, 8000);

        // Limit to 5 toasts
        while (toastContainer.children.length > 5) {
            toastContainer.removeChild(toastContainer.firstChild);
        }
    }

    // ─── Create Notification Card DOM ────────────────
    function createNotificationCard(data) {
        const card = document.createElement("div");
        card.className = `notification-card priority-${data.priority || "normal"}`;

        const categoryLabels = {
            fresher: "🎓 Fresher",
            training: "📚 Training",
            internship: "🎒 Intern",
            walk_in: "🚶 Walk-in",
            campus: "🏫 Campus",
            junior: "💼 Junior",
        };

        const regionLabels = {
            tamil_nadu: "🏛️ Tamil Nadu",
            karnataka: "🏙️ Karnataka",
            global: "🌍 Global",
        };

        const score = data.match_score || 0;
        const scorePercent = Math.round(score * 100);

        card.innerHTML = `
            <div class="notif-priority-stripe"></div>
            <div class="notif-content">
                <div class="notif-header">
                    <div class="notif-title-row">
                        <h3 class="notif-title">${escapeHtml(data.title || "Untitled")}</h3>
                        <span class="notif-badge category-${data.category || "unknown"}">
                            ${categoryLabels[data.category] || "📋 Job"}
                        </span>
                    </div>
                    <span class="notif-company">${escapeHtml(data.company || "Unknown")}</span>
                </div>
                <div class="notif-meta">
                    ${data.location ? `<span class="meta-item">📍 ${escapeHtml(data.location)}</span>` : ""}
                    ${data.region ? `<span class="meta-item region-tag">${regionLabels[data.region] || data.region}</span>` : ""}
                    ${data.is_fresher_eligible ? '<span class="meta-item fresher-tag">✅ Fresher Eligible</span>' : ""}
                </div>
                ${score > 0 ? `
                <div class="score-bar-container">
                    <div class="score-bar">
                        <div class="score-fill priority-${data.priority || "normal"}" style="width: ${scorePercent}%"></div>
                    </div>
                    <span class="score-text">${scorePercent}% match</span>
                </div>
                ` : ""}
                ${data.match_reason ? `<p class="notif-reason">${escapeHtml(data.match_reason)}</p>` : ""}
                <div class="notif-footer">
                    <span class="notif-time">${new Date().toLocaleString()}</span>
                    ${data.url ? `<a href="${escapeHtml(data.url)}" target="_blank" rel="noopener" class="apply-btn">Apply Now →</a>` : ""}
                </div>
            </div>
        `;

        return card;
    }

    // ─── Badge Updates ───────────────────────────────
    function updateBadges() {
        if (unreadBadge) {
            unreadBadge.textContent = unreadCount;
            unreadBadge.style.display = unreadCount > 0 ? "inline-block" : "none";
        }
        if (bellBadge) {
            bellBadge.textContent = unreadCount;
            bellBadge.style.display = unreadCount > 0 ? "inline-block" : "none";
        }
    }

    // ─── Notification Sound ──────────────────────────
    function playNotificationSound(priority) {
        // Create a subtle audio notification using Web Audio API
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.connect(gain);
            gain.connect(ctx.destination);

            // Different tones for different priorities
            const frequencies = {
                urgent: 880,
                hot: 660,
                good: 523,
                worth_checking: 440,
                new: 392,
                normal: 349,
            };

            osc.frequency.value = frequencies[priority] || 440;
            osc.type = "sine";
            gain.gain.value = 0.05; // Very subtle

            osc.start(ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            osc.stop(ctx.currentTime + 0.3);
        } catch (e) {
            // Audio not available, silently skip
        }
    }

    // ─── Sidebar Toggle ──────────────────────────────
    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (
                sidebar.classList.contains("open") &&
                !sidebar.contains(e.target) &&
                !menuToggle.contains(e.target)
            ) {
                sidebar.classList.remove("open");
            }
        });
    }

    // ─── Global Search ───────────────────────────────
    if (globalSearch) {
        let debounceTimer;
        globalSearch.addEventListener("input", () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = globalSearch.value.trim();
                if (query.length >= 2) {
                    window.location.href = `/jobs?q=${encodeURIComponent(query)}`;
                }
            }, 500);
        });

        globalSearch.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const query = globalSearch.value.trim();
                if (query) {
                    window.location.href = `/jobs?q=${encodeURIComponent(query)}`;
                }
            }
        });
    }

    // ─── Utility Functions ───────────────────────────
    function escapeHtml(str) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    // ─── Animate Score Bars on Scroll ────────────────
    function animateScoreBars() {
        const bars = document.querySelectorAll(".score-fill:not(.animated)");
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const fill = entry.target;
                        const width = fill.style.width;
                        fill.style.width = "0%";
                        fill.classList.add("animated");
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => {
                                fill.style.width = width;
                            });
                        });
                        observer.unobserve(fill);
                    }
                });
            },
            { threshold: 0.2 }
        );

        bars.forEach((bar) => observer.observe(bar));
    }

    // ─── Initialize ──────────────────────────────────
    function init() {
        connectSSE();
        animateScoreBars();

        // Fetch initial unread count
        fetch("/api/stats")
            .then((r) => r.json())
            .then((data) => {
                unreadCount = data.unread_count || 0;
                updateBadges();
            })
            .catch(() => {});
    }

    // ─── Pipeline Trigger ─────────────────────────────
    window.runPipelineNow = function () {
        const btn = document.getElementById("btn-run-pipeline");
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = "⏳ Scanning...";
        }

        showToast("Scanning 126 genuine company portals & dispatching email alerts to palulaptop@gmail.com...", "new");

        fetch("/api/pipeline/run", { method: "POST" })
            .then((r) => r.json())
            .then((data) => {
                showToast("✅ Scan complete! New fresher jobs updated.", "hot");
                setTimeout(() => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = "🔄 Refresh Jobs";
                    }
                    location.reload();
                }, 2000);
            })
            .catch((err) => {
                showToast("⚠️ Scan started in background.", "good");
                setTimeout(() => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = "🔄 Refresh Jobs";
                    }
                }, 3000);
            });
    };

    // Run on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
