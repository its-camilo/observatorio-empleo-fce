type Props = {
  className?: string;
};

/** Logo institucional UNAL: blanco sobre transparente (fondo institucional azul o marina). */
export default function LogoUnal({ className = "" }: Props) {
  return (
    <picture>
      <source type="image/webp" srcSet="/logo-unal-blanco.webp" />
      <img
        src="/logo-unal-blanco.png"
        alt="Universidad Nacional de Colombia"
        className={`h-16 w-auto max-w-[min(440px,72vw)] object-contain object-left md:h-[5.5rem] md:max-w-[560px] ${className}`}
        width={600}
        height={255}
        decoding="async"
      />
    </picture>
  );
}
