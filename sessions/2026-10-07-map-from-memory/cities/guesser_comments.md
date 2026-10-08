# What the guessers said

Each blind guesser (a fresh Claude Opus 5.5 subagent, no tools except reading its list and writing its answers) was asked to end with one honest sentence on how the task felt. Verbatim:

- **retest_1:** "Most places were big cities or towns I know well, so they were easy; the hard ones were Lagoa da Prata, Acará and "Fengxiang, Shanghai", which I suspect may really be Fengxian, so I gave those wide radii and marked them as not known."
- **retest_2:** "Most of these were big, well-known cities and felt easy; the hard ones were Inokura (Fukuoka), which I'd never heard of and placed only from its prefecture, Songjianghe (Jilin), which I only vaguely link to Fusong County, and to a lesser degree Saint-Lin-Laurentides, Maubara and Cuíto."
- **batch_2:** "Big and well-known cities like Melbourne, Madrid, Xi'an and Callao felt nearly automatic, but Babamba (Tshopo), Rayevskiy, Sang-e Chārak, Ōno (Iwate) and Tejar (which I associate with Cartago rather than San José) were real guesswork, so I gave them wide radii."
- **batch_3:** "Big cities like Cairo, Moscow, Lahore and Phoenix felt easy and certain, but I was really guessing on small places like Aporá in Bahia, Malango on Guadalcanal, Ngerengere in Tanzania and Boussé in Burkina Faso, so I gave those much wider radii."
- **batch_5:** "The capitals and big metros felt easy and I'm confident in them, but I was mostly reasoning from region for the small places: Hawsh Isa, the Shanghai "Fengxiang", Songjianghe, Bom Jesus do Tocantins, Poço Fundo, Lagoa da Prata, Koelwar and Erawan, so I gave those wide radii."
- **batch_6:** "Capitals and big cities like Omdurman, Kyoto and Hobart were easy, but Inokura (Fukuoka), Daxie (Chongqing), Quissecula (Kwanza Sul), Malingao (Philippines) and Shawei (Guangdong) were close to blind guesses, so I gave them wide radii."
- **batch_4:** "Most of these were easy: big cities and well-known towns like Bryansk, Jinju and Wadi Halfa felt solid. The hard ones were Patiriyat (I guessed it is Pathiriyad near Thalassery), Al Wāsiţah (I know it as Al Wasta in Beni Suef, not Faiyum), Mindouli (I know the one in Pool, not Likouala, so I gave it a 700 km r90) and São Lourenço (probably the Macau parish, though it is labelled Guangdong), so I widened those radii."
- **batch_1:** "Big cities and well-known towns (Verona, Torreón, Lusaka, Rotorua and others) came easily, but a few were real guesses: Unamaucheri, Londuimbali, Dêqên in Tibet and Degema Hulk. "Marāgheh, Razavi Khorasan" was the hardest, because the only Maragheh I know is in East Azerbaijan, so I put it there and gave it a very wide 90% radius."
- **precise_3** (batch 3 again, four decimals, fresh agent): "For big, well-known cities the third and fourth decimals felt like stored coordinates I was recalling, but for small places like Ngerengere, Aporá, Malango and Maubara they were plainly padding on top of a regional guess."

## Reverse lookup (coordinates in, place name out)

- **reverse_1:** "Big cities and distinctive towns came to mind almost instantly, but a few points sitting in rural Costa Rica, Sierra Leone and Afghanistan felt like guessing in the dark, and I tried to make the low probabilities say so."
- **reverse_2:** "The big cities felt like recognising old friends, but the suburbs and county seats in Tibet, Mindanao and Khorasan felt like guessing in fog, and I tried to let the probabilities show that."
- **reverse_3:** "Most points were big cities I recognised right away, and the hard part was the small towns in the Nile Delta, eastern DR Congo and inland Brazil, where my confidence really did drop low."
- **reverse_4:** "Big cities came back easily, but small suburbs and towns made me guess, especially places like Kerala census towns and the edges of Tokyo and Chennai, and I set lower probabilities for those."
- **reverse_5:** "The task felt good: the capitals and big cities came back as solid, clear memories, and I could feel my confidence fade to guesswork on the small towns in Rwanda, Thailand and Brazil."
- **reverse_6:** "The big cities felt like recognising faces, while small towns like the ones in rural Nigeria, northern Iwate or Fengxian felt like guessing in fog."

## Between the entries (arbitrary land point in, nearest town out)

- **between_1:** "It felt like walking a mental map that's sharp around big cities and goes foggy in the gaps between them, where I was often weighing two towns that seemed about equally close."
- **between_2:** "The remote and isolated points felt easy and solid, but suburban and very dense areas felt close to a coin toss, because there my answer depended on which suburbs and small towns the gazetteer happens to list."
- **between_3:** "I was sure of the places with a distinctive, well-known city right beside them, like Hämeenlinna or Kismayo, but in the suburbs and small-town Chinese clusters I was really guessing where a gazetteer draws its 15,000 line."
- **between_4:** "The empty places like the Nullarbor and the Arctic were easy, while the crowded suburbs and the question of which small towns a gazetteer counts as having 15,000 people felt like coin flips."
