import type { Preview } from "@storybook/nextjs-vite";
import "../src/app/globals.css";

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      test: "todo",
    },
    backgrounds: {
      default: "dark",
      values: [
        { name: "dark", value: "#07100e" },
        { name: "light", value: "#f2f6f3" },
      ],
    },
    layout: "padded",
  },
  decorators: [
    (Story, context) => {
      const bg = context.globals.backgrounds;
      const theme = bg?.value === "#f2f6f3" ? "light" : "dark";
      if (typeof document !== "undefined") {
        document.documentElement.dataset.theme = theme;
      }
      return <Story />;
    },
  ],
};

export default preview;
