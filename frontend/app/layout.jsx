import "./globals.css";

export const metadata = {
  title: "AXIOM | Autonomous Research Lab",
  description: "Explore hypotheses, run controlled experiments, and inspect evidence with AXIOM.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: "try{if(localStorage.getItem('axiom-theme')==='light')document.documentElement.dataset.theme='light'}catch(e){}" }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
