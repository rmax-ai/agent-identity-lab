<script>
  import { base } from "$app/paths";
  let { children } = $props();
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
</svelte:head>

<div class="min-h-screen bg-slate-950 text-slate-200 font-['Inter']">
  <nav class="fixed top-0 w-full z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
      <a href={base + "/"} class="flex items-center gap-2 font-semibold text-white no-underline">
        <span class="text-cyan-400 font-['JetBrains_Mono'] text-lg">◈</span>
        <span>Agent Identity Lab</span>
      </a>
      <div class="flex items-center gap-1 text-sm">
        <a href={base + "/"} class="px-3 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-slate-800/50 transition-colors no-underline">Home</a>
        <a href={base + "/architecture/"} class="px-3 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-slate-800/50 transition-colors no-underline">Architecture</a>
        <a href={base + "/phases/"} class="px-3 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-slate-800/50 transition-colors no-underline">Phases</a>
        <a href={base + "/api/"} class="px-3 py-1.5 rounded-md text-slate-300 hover:text-white hover:bg-slate-800/50 transition-colors no-underline">API</a>
        <a href="https://github.com/rmax-ai/agent-identity-lab" class="ml-2 px-3 py-1.5 rounded-md border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500 transition-colors no-underline text-xs font-['JetBrains_Mono']">GitHub ↗</a>
      </div>
    </div>
  </nav>
  <main class="pt-14">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 py-12">
      {@render children()}
    </div>
  </main>
  <footer class="border-t border-slate-800 py-8 text-center text-sm text-slate-600">
    <p>Agent Identity Lab · MIT License · <a href="https://github.com/rmax-ai/agent-identity-lab" class="text-slate-500 hover:text-cyan-400 transition-colors">rmax-ai/agent-identity-lab</a></p>
  </footer>
</div>

<style>
  :global(body) {
    margin: 0;
    background: #020617;
    color: #e2e8f0;
  }
  :global(a) {
    color: #22d3ee;
  }
  :global(code) {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.875em;
    background: rgba(30, 41, 59, 0.5);
    padding: 0.125em 0.375em;
    border-radius: 4px;
  }
  :global(pre) {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
  }
  :global(pre code) {
    background: none;
    padding: 0;
  }
  :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
  }
  :global(th) {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 2px solid #1e293b;
    color: #94a3b8;
    font-size: 0.875rem;
    font-weight: 500;
  }
  :global(td) {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #1e293b;
    font-size: 0.875rem;
  }
  :global(h1) {
    font-family: 'JetBrains Mono', monospace;
    color: white;
  }
  :global(h2), :global(h3), :global(h4) {
    font-family: 'JetBrains Mono', monospace;
    color: #e2e8f0;
  }
</style>
