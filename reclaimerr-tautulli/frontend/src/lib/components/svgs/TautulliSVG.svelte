<script lang="ts">
  let className: string = "";
  export { className as class };
  export let style: string = "";
</script>

<svg
  class={className}
  {style}
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 100 100"
  width="100"
  height="100"
  fill="none"
>
  <circle cx="50" cy="50" r="48" fill="#272b33" />
  <path
    d="M50 14 C70 14, 86 30, 86 50 C86 70, 70 86, 50 86 C30 86, 14 70, 14 50 C14 30, 30 14, 50 14 Z"
    fill="none"
    stroke="#e5a00d"
    stroke-width="4"
  />
  <path
    d="M50 22 L50 50 L72 60"
    fill="none"
    stroke="#e5a00d"
    stroke-width="5"
    stroke-linecap="round"
    stroke-linejoin="round"
  />
  <circle cx="50" cy="50" r="4" fill="#e5a00d" />
</svg>
