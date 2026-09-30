// Native details work without JavaScript; hash links also open their direction.
(() => {
  const revealDirection = () => {
    const group = document.getElementById(window.location.hash.slice(1));
    if (group && group.matches("details[data-topic-group]")) {
      group.open = true;
      group.scrollIntoView({ block: "start" });
    }
  };
  window.addEventListener("hashchange", revealDirection);
  revealDirection();
})();
