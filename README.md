# Stroke Scribbler

![Behold the welcoming header image](TKTKTK)

**This is an extension for RoboFont, the font editor for adults. It creates a live, non-destructive visualisation of a zig-zag, scribble hatching movement in the glyph window to emphasise the *surface of the stroke* rather than its outlines.**

**It mimicks the method of sketching letter shapes by hand that Gerritt Norrdzij used to teach (inter alii)**

**The visualisation can also be generated as a path, for example for use with [SingleLine otf-svgMaker](https://github.com/isdat-type/SingleLine_otf-svgMaker) by [Frederik Berlaen](https://github.com/typemytype) and [isdat-type](https://github.com/isdat-type).**

**This plugin works with *RoboFont version 4.4 and above*.**



## Interface and functionality


The extension is launched from RoboFont’s `Extensions` menu and will present this handsome window:

![Behold the Stroke Scribbler palette](TKTKTK)

**Add Contour Group / Delete Contour Group**

In an open Glyph Window, select **pairs** of **open**, **interpolateable** contours. Pressing `Add Contour Group` will add the contour pair to the Group Table where you can see its scribble settings. While selected in the Group Table, contour pairs can be edited with the settings below. 

Changes to the scribble settings will update in real time, and modifications in the Glyph Window of any contour from the Group Table will also update the visualisation in real time.



### Settings

- **Thickness** determines the thickness of the scribble line visualisation.
- **Distance** of scribble lines. Lower Distance = more dense scribbles. (Nerds: distance is the segment length of a customised flattenPen)
- **Offset** the first scribble line by skipping over a few corresponding points on the other contour. More Offset = more diagonal.
- **Random** offsets of the scribbler points from the precisely calculated position to focus even more away from the exact outline.
- Begin scribble on: 	**Left | Right** contour is the starting point of the scribble. That’s “right” or “left” in path direction.

- ✅ **Preview** turn the visualizer off or on. You can change the color with the adjacent color well.

### Generate Contours

**Generate Contours** will generate an open contour with the heartline of all scribbles in the current glyph’s GroupTable in a layer named `StrokeScribbler.drawing`. If the layer does not exist, it will be provided for you. If the layer already exists and already has contours in it for the current glyph, it will be emptied of those prior contours free of charge.

Among other things, the open single line contours can be processed with the [Outliner](https://github.com/typemytype/outlinerRoboFontExtension) extension or the [SingleLine otf-svgMaker](https://github.com/isdat-type/SingleLine_otf-svgMaker) by [Frederik Berlaen](https://github.com/typemytype) and [isdat-type](https://github.com/isdat-type).


## Origin and credits

Stroke Scribbler is a result of the research project **[Beyond Bézier](https://beyondbezier.ch)**, jointly organised by [ECAL](https://ecal.ch/) (University of Art and Design Lausanne) and [HEIA-FR](https://www.heia-fr.ch/) (Haute école d’ingénierie et d’architecture de Fribourg) and has been supported by [HES-SO](https://www.hes-so.ch/accueil), Réseau de Compétences Design et Arts Visuels.

Research for **Beyond Bézier** was carried out by by Matthieu Cortat-Roller, Alice Savoie, Kai Bernau, Radim Peško, Micha Wasem and Florence Yerly. The project started in September 2023 and was completed in May 2025. Raphaela Haefliger and Roland Früh were responsible for coordination and Nicolas Bernklau for design.

The StrokeScribbler is a result of the project’s research axis *The Stroke* by [Kai Bernau](https://kaibernau.com). It was programmed and will be maintained by [Connor Davenport](https://connordavenport.com). 

Stroke Scribbler makes use of [Mervyn Dow](https://gist.github.com/eevee)’s [Perlin Noise Generator](https://gist.github.com/eevee/26f547457522755cb1fb8739d0ea89a1) and [Roberto Arista](https://gist.github.com/roberto-arista)’s [implementation](https://discord.com/channels/1052516637489766411/1205447799651434496/1205516038549016626) of that generator into a [fontTools](https://github.com/fonttools/fonttools) pen, as well as [Erik van Blokland]()’s [Subscriber Event extractor code](https://github.com/LettError/longboardRoboFontExtension/blob/b2435510549883573b0268eaff28adc5f3a979c5/source/lib/longboard.py#L1374C1-L1394C15)


## Copyright and License

Stroke Scribbler Copyright © 2025 ECAL, Kai Bernau, Connor Davenport.

Released under [TKTKTKTKTKTKTK](https://example.com) license.


### Libraries

[mojo](https://www.robofont.com/documentation/reference/mojo/)  
Copyright © 2025 TypeMyType  

[fontPens](https://github.com/robotools/fontPens)  
Copyright © 2005-2017, The RoboFab Developers:  
Erik van Blokland  
Tal Leming  
Just van Rossum  

[fontTools](https://github.com/fonttools/fonttools)  
Copyright © 2017 Just van Rossum

[defcon](https://github.com/robotools/defcon)  
Copyright © 2005-2016 Type Supply LLC

[vanilla](https://github.com/robotools/vanilla)  
Copyright © 2005-2009 Tal Leming, Just van Rossum

[ezui](https://typesupply.github.io/ezui/)  
Copyright © 2021, Tal Leming

[Perlin Noise Generator](https://gist.github.com/eevee/26f547457522755cb1fb8739d0ea89a1)  
Copyright © 2024 Mervyn Dow


