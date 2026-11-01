/* Logo : l'escargot de Paris + « Lotent ». La spirale suit la couleur du texte,
   le point (l'événement) prend la couleur de marque (--brand). */
import React from "react";
import { SPIRAL, END } from "./logo-geometry.mjs";

export const LogoMark = ({ size = 28, className = "" }) =>
  <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
    <path d={SPIRAL} stroke="currentColor" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx={END[0]} cy={END[1]} r="4.6" className="fill-brand" /></svg>;

export const Logo = () => <span className="inline-flex items-center gap-2.5"><LogoMark /><span className="font-serif text-2xl font-medium leading-none">Lotent</span></span>;
