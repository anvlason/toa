#!/usr/bin/perl

foreach my $tif(glob("$ARGV[0]/*/*_3B_AnalyticMS.tif"))
{
  system("proc_planet_ps_s.py $tif");
}
