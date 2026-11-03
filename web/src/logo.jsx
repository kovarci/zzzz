/* Logo : spirale « coup de pinceau » + « Lotent ». La spirale suit la couleur du texte,
   le point (l'événement) prend la couleur de marque (--brand).
   Le dessin vient de logo.json : node logo-ideas/apply.mjs <id> change de variante (voir logo-ideas/README.md). */
import React from "react";
import logo from "./logo.json";

const [vx, vy, vs] = logo.view;
export const LogoMark = ({ size = 28, className = "" }) =>
  <svg width={size} height={size} viewBox={`${vx} ${vy} ${vs} ${vs}`} aria-hidden="true" className={className}>
    <g fill="currentColor">{logo.ink.map((d, i) => <path key={i} d={d} />)}</g>
    <g className="fill-brand">{logo.dot.map((d, i) => <path key={i} d={d} />)}</g></svg>;

export const Logo = () => <span className="inline-flex items-center gap-2.5"><LogoMark /><span className="font-serif text-2xl font-medium leading-none">Lotent</span></span>;
