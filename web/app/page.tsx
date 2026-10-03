import { FinalCta, Footer, Hero, HowItWorks, Marquee, Pillars, Proof, SiteNav, Trust } from "@/components/landing/sections";

export default function Home() {
  return (
    <>
      <SiteNav />
      <main>
        <Hero />
        <Marquee />
        <Pillars />
        <HowItWorks />
        <Proof />
        <Trust />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
