# Important safety information

Lithium-ion batteries store a lot of energy. Misuse can cause fire, burns or explosion. Read and follow these instructions.

**Battery**

- Use only new, unprotected 18650 lithium-ion cells from a reputable manufacturer, rated for at least 5 A continuous discharge (higher-rated cells run cooler and last longer). Never use cells that are swollen, dented, leaking or hot, or that have a torn or damaged wrap.
- Every cell must be the same make, model, capacity and age. Charge them to the same voltage (within 0.1 V) before fitting. On the QUAD pack the paired cells are joined directly, so two cells at different voltages pass a large current between them the moment they are fitted.
- Fit cells only with the pack's switch OFF, following the + marks in each holder. Half the holders face the other way.
- Other packs: use only 2S lithium-ion packs that have their own protection circuit (BMS), with an XT30 plug wired to the standard (+ to the contact marked +). The HAT has no reverse-polarity protection, and a pack wired backwards will damage it.
- The board cannot measure battery temperature. The pack switches itself off above about 60 °C, but nothing stops charging in the cold: charge only between 0 °C and 45 °C, and keep the cells away from direct sunlight and from heat sources, including the board itself.
- Do not short the cell terminals, the pack's test pads or the XT30 contacts.
- Do not leave a charging battery near flammable materials.

**Board**

- Disconnect the battery and USB-C power before fitting or removing the board, or touching anything on the Pi's header.
- The inductors and power ICs become hot to the touch at full 5 A load. Do not touch them while operating, and allow airflow around the board.
- Do not operate the board in an enclosure without ventilation, near water, or in condensing humidity.
- Use a USB-C power adapter from a reputable manufacturer, certified to your country's safety standards.
- Handle the board by its edges and use anti-static precautions. Electrostatic discharge can damage the components.
- Do not modify the boards or replace the pack's fuse with a higher rating.

**Intended use:** this is a power accessory for a Raspberry Pi in indoor, non-critical applications. Do not use it in medical, life-support or safety-critical equipment.

If the board or battery smells of burning, smokes, or becomes unusually hot, disconnect USB-C power, then disconnect the battery if it is safe to do so, and move away from it.
