"use strict";
(() => {
  let language = "en";
  try {
    language =
      localStorage.getItem("agentdog-dark-language") === "zh" ? "zh" : "en";
  } catch (_) {}
  const examples = window.AGENTDOG_EXAMPLES || [];
  let selectedCase = "goal";
  let selectedStage = 0;
  let replayTimer = null;
  const tr = (value) =>
    typeof value === "string" ? value : value?.[language] || value?.en || "";
  const t = (en, zh) => (language === "zh" ? zh : en);

  function stopReplay() {
    if (replayTimer) clearInterval(replayTimer);
    replayTimer = null;
    document
      .getElementById("replay-case")
      .setAttribute("aria-pressed", "false");
    document.querySelector("#replay-case span").textContent = t(
      "Play walkthrough",
      "播放演示",
    );
  }

  function renderCase() {
    const example = examples.find((x) => x.id === selectedCase);
    if (!example) return;
    const fields = {
      "case-title": "title",
      "case-task": "task",
      "case-action": "proposedAction",
      "case-decision": "guardDecision",
      "case-source": "source",
      "case-failure": "failure",
      "case-harm": "harm",
      "case-alternative": "safeAlternative",
      "case-disclaimer": "disclaimer",
    };
    Object.entries(fields).forEach(([id, key]) => {
      document.getElementById(id).textContent = tr(example[key]);
    });
    document.querySelectorAll("[data-case]").forEach((button) => {
      const active = button.dataset.case === selectedCase;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document
      .getElementById("case-panel")
      .setAttribute("aria-labelledby", `case-tab-${selectedCase}`);
    const timeline = document.getElementById("case-timeline");
    timeline.replaceChildren();
    example.steps.forEach((step, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.kind = step.kind;
      button.dataset.stageIndex = String(index);
      button.classList.toggle("active", selectedStage === index);
      button.setAttribute("aria-pressed", String(selectedStage === index));
      const marker = document.createElement("span");
      marker.className = "stage-marker";
      marker.setAttribute("aria-hidden", "true");
      marker.textContent =
        step.kind === "blocked" ? "✓" : step.kind === "risk" ? "!" : "◇";
      const label = document.createElement("span");
      label.textContent = tr(step.label);
      button.append(marker, label);
      button.addEventListener("click", () => {
        stopReplay();
        selectedStage = index;
        renderStage();
      });
      timeline.append(button);
    });
    renderStage();
  }

  function renderStage() {
    const example = examples.find((x) => x.id === selectedCase);
    if (!example) return;
    document.getElementById("case-stage").textContent = tr(
      example.steps[selectedStage].label,
    );
    document.querySelectorAll("[data-stage-index]").forEach((button) => {
      const active = Number(button.dataset.stageIndex) === selectedStage;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function renderLanguage() {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-en][data-zh]").forEach((el) => {
      el.innerHTML = el.dataset[language];
    });
    const languageButton = document.getElementById("language-toggle");
    languageButton.textContent = t("中文", "EN");
    languageButton.setAttribute(
      "aria-label",
      t("切换到中文", "Switch to English"),
    );
    document
      .getElementById("menu-toggle")
      .setAttribute("aria-label", t("Toggle navigation", "切换导航菜单"));
    document
      .getElementById("dialog-close")
      .setAttribute("aria-label", t("Close figure", "关闭图片"));
    document
      .getElementById("back-to-top")
      .setAttribute("aria-label", t("Back to top", "回到顶部"));
    document.title = t(
      "AgentDoG 2.0 | Long-Horizon Agent Safety & Security",
      "AgentDoG 2.0 | 面向长程任务的智能体安全",
    );
    renderCase();
  }

  document.getElementById("language-toggle").addEventListener("click", () => {
    stopReplay();
    language = language === "en" ? "zh" : "en";
    try {
      localStorage.setItem("agentdog-dark-language", language);
    } catch (_) {}
    renderLanguage();
  });
  document.querySelectorAll("[data-case]").forEach((button) =>
    button.addEventListener("click", () => {
      stopReplay();
      selectedCase = button.dataset.case;
      selectedStage = 0;
      renderCase();
    }),
  );
  document.querySelectorAll("[data-case]").forEach((button) =>
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const buttons = [...document.querySelectorAll("[data-case]")];
      let index = buttons.indexOf(button);
      if (event.key === "Home") index = 0;
      else if (event.key === "End") index = buttons.length - 1;
      else
        index =
          (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) %
          buttons.length;
      buttons[index].click();
      buttons[index].focus();
    }),
  );
  document.getElementById("replay-case").addEventListener("click", () => {
    if (replayTimer) {
      stopReplay();
      return;
    }
    selectedStage = 0;
    renderStage();
    document.getElementById("replay-case").setAttribute("aria-pressed", "true");
    document.querySelector("#replay-case span").textContent = t(
      "Pause walkthrough",
      "暂停演示",
    );
    replayTimer = setInterval(() => {
      selectedStage += 1;
      if (selectedStage >= 4) {
        selectedStage = 3;
        stopReplay();
      }
      renderStage();
      if (selectedStage === 3) stopReplay();
    }, 1400);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopReplay();
  });

  document.querySelectorAll("[data-model-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      const filter = button.dataset.modelFilter;
      document.querySelectorAll("[data-model-filter]").forEach((other) => {
        other.classList.toggle("active", other === button);
        other.setAttribute("aria-pressed", String(other === button));
      });
      document.querySelectorAll("[data-model-group]").forEach((row) => {
        row.hidden = filter !== "all" && row.dataset.modelGroup !== filter;
      });
    }),
  );

  const nav = document.getElementById("nav-links");
  const menu = document.getElementById("menu-toggle");
  const versions = document.getElementById("version-picker");
  const closeNav = () => {
    nav.classList.remove("open");
    menu.setAttribute("aria-expanded", "false");
  };
  menu.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    menu.setAttribute("aria-expanded", String(open));
    versions.open = false;
  });
  nav
    .querySelectorAll("a")
    .forEach((link) => link.addEventListener("click", closeNav));
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".nav")) {
      closeNav();
      versions.open = false;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeNav();
      versions.open = false;
      stopReplay();
    }
  });

  const topButton = document.getElementById("back-to-top");
  window.addEventListener(
    "scroll",
    () => {
      topButton.hidden = scrollY < 800;
    },
    { passive: true },
  );
  topButton.addEventListener("click", () =>
    window.scrollTo({
      top: 0,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    }),
  );
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          nav.querySelectorAll("a").forEach((link) => {
            if (link.getAttribute("href") === `#${entry.target.id}`)
              link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
          });
        });
      },
      { rootMargin: "-12% 0px -65% 0px" },
    );
    document
      .querySelectorAll("main>section[id]")
      .forEach((section) => observer.observe(section));
  }

  const dialog = document.getElementById("figure-dialog");
  const canvas = dialog.querySelector(".dialog-canvas");
  let previousFocus = null;
  document.querySelectorAll("[data-figure]").forEach((button) =>
    button.addEventListener("click", () => {
      previousFocus = button;
      const image = document.getElementById("dialog-image");
      image.src = button.dataset.figure;
      image.alt =
        button.querySelector("img")?.alt || button.dataset.figureTitle;
      document.getElementById("dialog-title").textContent =
        button.dataset.figureTitle;
      canvas.classList.remove("actual-size");
      document.getElementById("dialog-zoom").textContent = t(
        "Actual size",
        "原始尺寸",
      );
      dialog.showModal();
    }),
  );
  document
    .getElementById("dialog-close")
    .addEventListener("click", () => dialog.close());
  document.getElementById("dialog-zoom").addEventListener("click", () => {
    const actual = canvas.classList.toggle("actual-size");
    document.getElementById("dialog-zoom").textContent = actual
      ? t("Fit to window", "适应窗口")
      : t("Actual size", "原始尺寸");
  });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    if (previousFocus) previousFocus.focus();
  });
  renderLanguage();
  stopReplay();
})();
