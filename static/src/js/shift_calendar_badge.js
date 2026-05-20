/** @odoo-module **/

import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { patch } from "@web/core/utils/patch";

patch(CalendarRenderer.prototype, {
    mounted() {
        super.mounted();
        this._addShiftStateBadges();
    },

    patched() {
        super.patched();
        this._addShiftStateBadges();
    },

    _addShiftStateBadges() {
        const events = this.el.querySelectorAll(".fc-event");

        events.forEach((eventEl) => {
            if (eventEl.querySelector(".t4-shift-state-badge")) {
                return;
            }

            const text = eventEl.innerText || "";

            let state = null;

            if (text.includes("[open]")) {
                state = "Open";
            } else if (text.includes("[draft]")) {
                state = "Draft";
            } else if (text.includes("[cancel]")) {
                state = "Cancel";
            }

            if (!state) {
                return;
            }

            const badge = document.createElement("span");
            badge.classList.add("t4-shift-state-badge");

            if (state === "Open") {
                badge.classList.add("t4-state-open");
            } else if (state === "Draft") {
                badge.classList.add("t4-state-draft");
            } else if (state === "Cancel") {
                badge.classList.add("t4-state-cancel");
            }

            badge.textContent = state;

            const titleEl =
                eventEl.querySelector(".fc-event-title") ||
                eventEl.querySelector(".fc-event-main") ||
                eventEl;

            titleEl.appendChild(badge);
        });
    },
});