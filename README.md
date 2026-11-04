# CrossyQ - Reinforcement Learning

Jeu 2D inspiré de Crossy Road, réalisé avec Pygame.

## Lancer le jeu

Installez Pygame (`pip install pygame-ce`, ou `pip install pygame`), puis lancez :

```bash
python3 main.py
```

Au menu, appuyez sur **I** pour démarrer avec le pilote automatique. En partie,
**I** active ou désactive l'IA ; les déplacements manuels restent disponibles
lorsqu'elle est désactivée.

## Comment joue l'IA

Le pilote de `ai.py` est un agent à règles explicites, sans entraînement. À
chaque décision, il examine les déplacements possibles et vérifie leur arrivée
sur l'herbe, les nénuphars et les bûches. Il prédit aussi les positions des
véhicules et des trains pendant le saut, puis privilégie les déplacements sûrs
qui font avancer le joueur. Les règles sont séparées en petites fonctions pour
faciliter leur lecture et leur modification.
