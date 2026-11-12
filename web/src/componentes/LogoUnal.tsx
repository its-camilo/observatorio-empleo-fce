type Props = {
  className?: string;
};

/** Logo institucional UNAL: blanco sobre transparente (usar sobre fondo oscuro #042361). */
export default function LogoUnal({ className = "" }: Props) {
  return (
    <picture>
      <source type="image/webp" srcSet="/logo-unal-blanco.webp" />
      <img
        src="/logo-unal-blanco.png"
        alt="Universidad Nacional de Colombia"
        className={`h-8 w-auto max-w-[min(220px,55vw)] object-contain object-left md:h-11 md:max-w-[280px] ${className}`}
        width={600}
        height={255}
        decoding="async"
      />
    </picture>
  );
}
