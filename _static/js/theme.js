const root = document.documentElement
const navbar = document.querySelector(".navbar")

// localStorage throws in a private window or with site data blocked

const load = (key) => {
  try { return localStorage.getItem(key) } catch { return null }
}

const store = (key, value) => {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {}
}

/* --- Navbar --- */

const hamburger = navbar.querySelector(".navbar-hamburger")
const links = navbar.querySelector(".navbar-links")
const more = navbar.querySelector(".navbar-more")
const moreButton = more?.querySelector(".navbar-more-button")

/** @param {boolean} opened */
function setMenuOpened(opened) {
  // Where the dimmed page under the open menu starts
  if (opened) root.style.setProperty("--menu-height", `${links.offsetHeight}px`)
  navbar.classList.toggle("opened", opened)
  document.body.classList.toggle("navbar-opened", opened)
  hamburger.setAttribute("aria-expanded", opened)
}

/** @param {boolean} opened */
function setMoreOpened(opened) {
  if (!more) return
  more.classList.toggle("opened", opened)
  moreButton.setAttribute("aria-expanded", opened)
}

hamburger.addEventListener("click", () => {
  setPanelOpened(false)
  setMenuOpened(!navbar.classList.contains("opened"))
})
moreButton?.addEventListener("click", () => setMoreOpened(!more.classList.contains("opened")))
navbar.querySelector(".navbar-backdrop").addEventListener("click", () => setMenuOpened(false))

document.addEventListener("click", (e) => {
  if (more && !more.contains(e.target)) setMoreOpened(false)
})

/* --- Theme --- */

const CHOICES = ["system", "light", "dark"]
const systemLight = matchMedia("(prefers-color-scheme: light)")

function applyTheme() {
  const choice = root.dataset.themeChoice
  const theme = choice === "system" ? (systemLight.matches ? "light" : "dark") : choice
  root.dataset.theme = theme
  document.querySelector("meta[name=theme-color]").content = theme === "light" ? "#f5f5f5" : "#303030"
}

const themeButton = navbar.querySelector(".theme-button")

function labelThemeButton() {
  const label = { system: "Theme: system", light: "Theme: light", dark: "Theme: dark" }[root.dataset.themeChoice]
  themeButton.title = label
  themeButton.setAttribute("aria-label", label)
}

themeButton.addEventListener("click", () => {
  const next = CHOICES[(CHOICES.indexOf(root.dataset.themeChoice) + 1) % CHOICES.length]
  root.dataset.themeChoice = next
  store("theme", next === "system" ? null : next)
  applyTheme()
  labelThemeButton()
})

systemLight.addEventListener("change", applyTheme)
labelThemeButton()

// A page prerendered on hover may have an outdated theme
document.addEventListener("prerenderingchange", () => {
  const stored = load("theme")
  root.dataset.themeChoice = stored === "light" || stored === "dark" ? stored : "system"
  applyTheme()
  labelThemeButton()
})

addEventListener("storage", (e) => {
  if (e.key !== "theme") return
  root.dataset.themeChoice = e.newValue === "light" || e.newValue === "dark" ? e.newValue : "system"
  applyTheme()
  labelThemeButton()
})

/* --- Contents panel --- */

const panel = document.querySelector(".panel")
const panelButton = navbar.querySelector(".panel-button")

/** @param {boolean} opened */
function setPanelOpened(opened) {
  if (!panel) return
  document.body.classList.toggle("panel-opened", opened)
  panelButton.setAttribute("aria-expanded", opened)
  if (opened) scrollPanelTo(panel.querySelector(".active, [aria-current]"), "center")
}

panelButton?.addEventListener("click", () => {
  setMenuOpened(false)
  setPanelOpened(!document.body.classList.contains("panel-opened"))
})
document.querySelector(".panel-backdrop")?.addEventListener("click", () => setPanelOpened(false))
panel?.addEventListener("click", (e) => {
  if (e.target.closest("a")) setPanelOpened(false)
})

/**
 * Scrolls only the panel, scrollIntoView would scroll the page too.
 * @param {Element | null} link
 * @param {"nearest" | "center"} [block]
 */
function scrollPanelTo(link, block = "nearest") {
  if (!panel || !link) return
  const box = panel.getBoundingClientRect()
  // The panel runs up under the navbar, that part isn't in view
  const top = Math.max(box.top, navbar.getBoundingClientRect().bottom)
  const item = link.getBoundingClientRect()
  const margin = 48
  if (block === "center") panel.scrollTop += item.top - top - (box.bottom - top) / 2 + item.height / 2
  else if (item.top < top + margin) panel.scrollTop -= top + margin - item.top
  else if (item.bottom > box.bottom - margin) panel.scrollTop += item.bottom - box.bottom + margin
}

// With a mouse .page scrolls, on a phone the window does (see theme.css)
const page = document.querySelector(".page")
const scroller = () => getComputedStyle(page).overflowY === "auto" ? page : document.scrollingElement

const tracked = panel
  ? [...panel.querySelectorAll(".panel-contents a[href^='#']")]
    .map((link) => ({ link, target: document.getElementById(decodeURIComponent(link.hash.slice(1))) }))
    .filter((t) => t.target)
  : []

let activeLink = null
let spyQueued = false

function spy() {
  spyQueued = false
  const line = navbar.offsetHeight + 24
  let current = null
  for (const t of tracked) {
    if (t.target.getBoundingClientRect().top <= line) current = t.link
    else break
  }
  // At the bottom, the last ones can't scroll up to the line
  const box = scroller()
  if (box.scrollTop + box.clientHeight >= box.scrollHeight - 2) current = tracked.at(-1).link
  if (current === activeLink) return
  activeLink?.classList.remove("active")
  current?.classList.add("active")
  activeLink = current
  if (!panel.matches(":hover")) scrollPanelTo(current)
}

if (tracked.length) {
  // Captured, a scroll in .page doesn't bubble
  document.addEventListener("scroll", (e) => {
    if (spyQueued || (e.target !== document && e.target !== page)) return
    spyQueued = true
    requestAnimationFrame(spy)
  }, { capture: true, passive: true })
  spy()
}

// The API section lists enough pages to push the current one out of view
if (panel) scrollPanelTo(panel.querySelector(".panel-pages [aria-current]"), "center")

/* --- Search, over Sphinx's searchindex.js --- */

const SHOWN = 30
const RECENT_KEY = "search-recent"
const RECENT_SHOWN = 5
const KIND_BONUS = { Page: 120, Class: 90, Exception: 70, Function: 50, Method: 40, Property: 40, Attribute: 30, Section: 20 }

const searchButton = navbar.querySelector(".search-button")
const modal = document.querySelector(".search-modal")
const input = modal.querySelector(".search-input")
const list = modal.querySelector(".search-results")
const note = modal.querySelector(".search-note")
const contentRoot = root.dataset.content_root ?? ""
const suffix = window.DOCUMENTATION_OPTIONS?.FILE_SUFFIX ?? ".html"

/**
 * @param {string} text
 * @returns {string} "Client.fetch_user" -> "client fetch user"
 */
const fold = (text) => text.normalize("NFD").replace(/[̀-ͯ'’]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()

/**
 * @typedef {object} Entry
 * @property {string} name
 * @property {string} [detail] The module or page
 * @property {string} kind
 * @property {string} url Relative to the docs' root
 * @property {string} key The name folded
 * @property {string[]} words
 * @property {string} text The key and detail folded
 */

/**
 * @param {Omit<Entry, "key" | "words" | "text">} entry
 * @returns {Entry}
 */
function searchable(entry) {
  const key = fold(entry.name)
  return { ...entry, key, words: key.split(" "), text: `${key} ${fold(entry.detail ?? "")}` }
}

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1)

/**
 * @param {object} index
 * @returns {Entry[]}
 */
function entriesOf(index) {
  const page = (doc) => `${index.docnames[doc]}${suffix}`
  const all = []

  for (const [doc, title] of index.titles.entries()) {
    all.push(searchable({ name: title, kind: "Page", url: page(doc) }))
  }

  for (const [title, places] of Object.entries(index.alltitles ?? {})) {
    for (const [doc, anchor] of places) {
      if (!anchor) continue
      all.push(searchable({ name: title, detail: index.titles[doc], kind: "Section", url: `${page(doc)}#${anchor}` }))
    }
  }

  for (const [prefix, objects] of Object.entries(index.objects ?? {})) {
    for (const [doc, type, prio, anchor, name] of objects) {
      if (prio < 0) continue
      const fullname = prefix ? `${prefix}.${name}` : name
      const kind = capitalise(index.objnames[type]?.[1] ?? "object")
      const hash = anchor === "" ? fullname : anchor === "-" ? `${index.objnames[type][1]}-${fullname}` : anchor
      // discord_http.client.Client.fetch_user shows as Client.fetch_user
      const parts = prefix.split(".")
      const owner = parts.at(-1)
      const shown = owner && /^[A-Z]/.test(owner) ? `${owner}.${name}` : name
      const module = (owner && /^[A-Z]/.test(owner) ? parts.slice(0, -1) : parts).join(".")
      all.push(searchable({ name: shown, detail: module, kind, url: `${page(doc)}#${hash}` }))
    }
  }

  return all
}

const startsWord = (key, i) => i === 0 || key[i - 1] === " "

/**
 * The word's letters in order through the key, like "gcm" in "get channel message".
 * @param {string} word
 * @param {string} key
 * @param {boolean} [jump]
 * @returns {number} 0 when they aren't there, up to 3 a letter for word starts and letters in a row
 */
function abbreviation(word, key, jump = true) {
  let pos = -1
  let points = 0
  for (let i = 0; i < word.length; i++) {
    let at = key.indexOf(word[i], pos + 1)
    if (at < 0) return jump ? abbreviation(word, key, false) : 0
    if (i === 0 || (jump && at !== pos + 1)) {
      let start = at
      while (start >= 0 && !startsWord(key, start)) start = key.indexOf(word[i], start + 1)
      if (start >= 0) at = start
      else if (i === 0) return 0
    }
    points += startsWord(key, at) ? 3 : at === pos + 1 ? 2 : 1
    pos = at
  }
  return points
}

/**
 * @param {Entry} entry
 * @param {string} word
 * @returns {number}
 */
function wordScore(entry, word) {
  if (entry.words.includes(word)) return 100
  if (entry.words.some((w) => w.startsWith(word))) return 80
  if (entry.key.includes(word)) return 50
  if (entry.text.includes(word)) return 40
  if (word.length < 2) return 0
  const points = abbreviation(word, entry.key)
  return points && 10 + points / word.length * 9
}

/**
 * Every word of the query has to be in it.
 * @param {Entry} entry
 * @param {string} query Folded
 * @param {string[]} words
 * @returns {number} 0 when it doesn't match
 */
function score(entry, query, words) {
  let total = 0
  for (const word of words) {
    const points = wordScore(entry, word)
    if (!points) return 0
    total += points
  }
  const key = ` ${entry.key} `
  if (entry.key === query) total += 500
  // "fetch user" finds Client.fetch_user before Client.fetch_users
  else if (entry.words.length > 1 && entry.words.slice(1).join(" ") === query) total += 400
  else if (key.endsWith(` ${query} `)) total += 200
  else if (key.includes(` ${query} `)) total += 150
  else if (entry.key.startsWith(query)) total += 100
  return total + (KIND_BONUS[entry.kind] ?? 0)
}

/**
 * @param {Entry[]} entries
 * @param {string} text
 * @returns {Entry[]}
 */
function rank(entries, text) {
  const query = fold(text)
  const words = query.split(" ").filter(Boolean)
  if (!query) return []
  return entries
    .map((entry) => ({ entry, rank: score(entry, query, words) }))
    .filter((e) => e.rank > 0)
    .sort((a, b) => b.rank - a.rank || a.entry.key.length - b.entry.key.length)
    .slice(0, SHOWN)
    .map((e) => e.entry)
}

/** @type {Promise<Entry[]> | null} */
let loading = null
/** @type {Entry[]} */
let entries = []
/** @type {Map<string, Entry>} */
let byUrl = new Map()
/** @type {Array<Entry | { fulltext: string }>} */
let shown = []
let active = 0

/**
 * Loaded as a script rather than fetched, so it works from file:// too. Sphinx's search page loads it itself.
 * @returns {Promise<Entry[]>}
 */
function loadIndex() {
  loading ??= new Promise((resolve, reject) => {
    // searchtools.js's, a top level const rather than on window
    const sphinx = typeof Search === "undefined" ? null : Search
    if (sphinx?._index) return resolve(sphinx._index)

    if (sphinx) {
      const setIndex = sphinx.setIndex
      sphinx.setIndex = (index) => {
        setIndex(index)
        resolve(index)
      }
      return
    }

    window.Search = { setIndex: resolve }
    const script = document.createElement("script")
    script.src = searchButton.dataset.index
    script.onerror = () => {
      script.remove()
      reject(new Error("The search index didn't load"))
    }
    document.head.append(script)
  })
    .then(entriesOf)
    .catch((e) => {
      loading = null
      throw e
    })
  return loading
}

/** @param {number} i */
function setActive(i) {
  if (!shown.length) return
  active = (i + shown.length) % shown.length
  for (const [j, li] of [...list.children].entries()) li.setAttribute("aria-selected", j === active)
  const li = list.children[active]
  input.setAttribute("aria-activedescendant", li.id)
  li.scrollIntoView({ block: "nearest" })
}

/** @returns {string[]} Newest first */
function recentUrls() {
  try {
    const urls = JSON.parse(load(RECENT_KEY))
    return Array.isArray(urls) ? urls : []
  } catch {
    return []
  }
}

/** @param {string} url */
function remember(url) {
  store(RECENT_KEY, JSON.stringify([url, ...recentUrls().filter((u) => u !== url)].slice(0, RECENT_SHOWN)))
}

const fullTextUrl = (text) => `${searchButton.dataset.search}?q=${encodeURIComponent(text)}`

/**
 * @param {Entry | { fulltext: string }} item
 * @param {number} i
 * @returns {HTMLLIElement}
 */
function row(item, i) {
  const li = document.createElement("li")
  li.id = `search-result-${i}`
  li.setAttribute("role", "option")
  const a = document.createElement("a")
  a.className = "search-result"
  const name = document.createElement("span")
  name.className = "search-name"
  const kind = document.createElement("span")
  kind.className = "search-kind"

  if ("fulltext" in item) {
    a.href = fullTextUrl(item.fulltext)
    a.classList.add("search-fulltext")
    name.textContent = `All results for “${item.fulltext}”`
    kind.textContent = "Every page"
    a.append(name, kind)
  } else {
    a.href = contentRoot + item.url
    a.dataset.url = item.url
    name.textContent = item.name
    kind.textContent = item.kind
    a.append(name)
    if (item.detail) {
      const detail = document.createElement("span")
      detail.className = "search-detail"
      detail.textContent = item.detail
      a.append(detail)
    }
    a.append(kind)
  }

  li.append(a)
  return li
}

function update() {
  const typed = input.value.trim()
  const results = typed ? rank(entries, typed) : recentUrls().map((url) => byUrl.get(url)).filter(Boolean)
  shown = typed ? [...results, { fulltext: typed }] : results
  list.replaceChildren(...shown.map(row))
  note.textContent = typed
    ? results.length ? "" : "Nothing by that name, all results looks inside the pages too."
    : results.length ? "" : "Classes, methods, pages and sections. Ctrl+K opens this from anywhere."
  list.dataset.label = typed ? "" : results.length ? "Recent" : ""
  active = 0
  if (shown.length) setActive(0)
  else input.removeAttribute("aria-activedescendant")
}

async function openSearch() {
  setMenuOpened(false)
  setPanelOpened(false)
  if (!modal.open) modal.showModal()
  input.select()
  if (entries.length) return update()
  note.textContent = "Loading…"
  try {
    entries = await loadIndex()
    byUrl = new Map(entries.map((e) => [e.url, e]))
    update()
  } catch {
    note.textContent = "The search index couldn't be loaded, try again in a moment."
  }
}

searchButton.addEventListener("click", openSearch)
const preload = () => loadIndex().catch(() => {})
searchButton.addEventListener("pointerenter", preload, { once: true })
searchButton.addEventListener("focus", preload, { once: true })

input.addEventListener("input", update)

input.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault()
    setActive(active + (e.key === "ArrowDown" ? 1 : -1))
  } else if (e.key === "Enter" && shown.length) {
    e.preventDefault()
    list.children[active].querySelector("a").click()
  }
})

list.addEventListener("click", (e) => {
  const a = e.target.closest("a")
  if (!a) return
  if (a.dataset.url) remember(a.dataset.url)
  // An anchor on the same page doesn't navigate, which would have closed it
  modal.close()
})

// The backdrop
modal.addEventListener("click", (e) => {
  if (e.target === modal) modal.close()
})

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault()
    if (modal.open) modal.close()
    else openSearch()
    return
  }
  // Unless typing somewhere
  if (e.key === "/" && !modal.open && !e.target.closest("input, textarea, select, [contenteditable]")) {
    e.preventDefault()
    openSearch()
    return
  }
  if (e.key === "Escape") {
    setMenuOpened(false)
    setMoreOpened(false)
    setPanelOpened(false)
  }
})
