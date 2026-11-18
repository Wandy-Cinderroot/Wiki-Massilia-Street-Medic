---
title: Relation entre catégories
---
# Pourquoi cet ordre
Connaître à l'avance les moyens employés permet de savoir comment s'équiper pour soigner en sécurité. Une fois la théorie acquise, on peut apprendre à se coordonner en équipe.
```mermaid
flowchart LR
    R["1 - Reconnaître"] -->|"permet d'anticiper"| E["2 - Équiper"]
    E -->|"permet de soigner en sécurité"| S["3 - Soigner"]
    S -->|"théorie complète"| A["4 - Agir en équipe"]
    A -->|"à emporter"| RES["5 - Ressources : affiches"]
```
1. Reconnaître : identifier les moyens employés.
2. Équiper : choisir la protection adaptée.
3. Soigner : savoir quoi faire selon la gravité.
4. Agir : coordonner l'équipe avant, pendant, après.
5. Ressources : emporter les affiches imprimables.
# Carte des liens
Comment les unités, les armes, les munitions et les véhicules se relient aux blessures.
```mermaid
flowchart TD
    U[Unité] -->|emploie| AC[Arme de contact]
    U -->|emploie| L[Lanceur]
    U -->|utilise| V[Véhicule]
    V -->|porte| L
    L -->|tire| M[Munition]
    U -->|lance à la main| M
    AC -->|cause| B[Blessure]
    M -->|cause| B
    B -->|se traite par| S[Soin]
    B -->|se prévient par| P[Protection]
```
