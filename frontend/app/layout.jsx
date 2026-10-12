import "./globals.css";

export const metadata = {
  title: "AXIOM | Research Console",
  description: "Explore hypotheses, run controlled experiments, and inspect evidence with AXIOM.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
