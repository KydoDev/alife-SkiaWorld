// G3 P6b: the population screen's data. Cells per kind are counted from the ABI 4 tile words (ADR-0016), and a
// bounded history keeps the whole run: when it is full, every other sample is dropped and the sampling interval
// doubles, so memory stays fixed and the chart always spans step 0 to now. Pure, so EditMode tests check it.
using System;
using System.Collections.Generic;

namespace WorldSim
{
    public static class Population
    {
        /// <summary>Cells per kind: index 1 photo, 2 sapro, 3 pred, 4 chemo (index 0, empty tiles, is unused).
        /// </summary>
        public static int[] Count(byte[] tiles)
        {
            if (tiles.Length % 4 != 0)
            {
                throw new ArgumentException("tile words are 4 bytes each", nameof(tiles));
            }
            var counts = new int[5];
            for (int i = 0; i < tiles.Length; i += 4)
            {
                int kind = tiles[i] & 0x7;
                if (kind >= 1 && kind <= 4)
                {
                    counts[kind]++;
                }
            }
            counts[0] = 0;
            return counts;
        }
    }

    /// <summary>Samples of the counts per kind over a run, at most <see cref="Capacity"/> of them.</summary>
    public sealed class PopulationHistory
    {
        public readonly struct Sample
        {
            public readonly ulong Step;
            public readonly int Photo, Sapro, Pred, Chemo;

            public Sample(ulong step, int[] counts)
            {
                Step = step;
                Photo = counts[1];
                Sapro = counts[2];
                Pred = counts[3];
                Chemo = counts[4];
            }

            public int this[int kind] => kind switch { 1 => Photo, 2 => Sapro, 3 => Pred, 4 => Chemo, _ => 0 };
        }

        private readonly List<Sample> _samples = new List<Sample>();

        public int Capacity { get; }

        /// <summary>Steps between kept samples (1 at first, doubled each time the history is thinned).</summary>
        public ulong Interval { get; private set; } = 1;

        public IReadOnlyList<Sample> Samples => _samples;

        public PopulationHistory(int capacity = 240)
        {
            if (capacity < 2)
            {
                throw new ArgumentOutOfRangeException(nameof(capacity), "at least two samples");
            }
            Capacity = capacity;
        }

        public void Clear()
        {
            _samples.Clear();
            Interval = 1;
        }

        /// <summary>Record the counts at <paramref name="step"/>; skipped unless at least <see cref="Interval"/>
        /// steps after the last kept sample. A step before the last one (a new world) restarts the history.</summary>
        public void Add(ulong step, int[] counts)
        {
            if (_samples.Count > 0)
            {
                ulong last = _samples[_samples.Count - 1].Step;
                if (step < last)
                {
                    Clear();
                }
                else if (step - last < Interval)
                {
                    return;
                }
            }
            _samples.Add(new Sample(step, counts));
            if (_samples.Count > Capacity)
            {
                // keep samples 0, 2, 4, ... and the newest: the chart still starts at the first step
                var kept = new List<Sample>(Capacity);
                for (int i = 0; i < _samples.Count - 1; i += 2)
                {
                    kept.Add(_samples[i]);
                }
                kept.Add(_samples[_samples.Count - 1]);
                _samples.Clear();
                _samples.AddRange(kept);
                Interval *= 2;
            }
        }

        /// <summary>The largest count of any kind in the history (the chart's top), at least 1.</summary>
        public int Peak()
        {
            int peak = 1;
            foreach (Sample s in _samples)
            {
                peak = Math.Max(peak, Math.Max(Math.Max(s.Photo, s.Sapro), Math.Max(s.Pred, s.Chemo)));
            }
            return peak;
        }
    }
}
