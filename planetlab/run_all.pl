#!/usr/bin/perl

foreach my $tif(glob("$ARGV[0]/*/*_3B_AnalyticMS.tif"))
{
  system("proc_planet.py $tif");
}
