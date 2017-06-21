#!/usr/bin/perl

foreach my $tif(glob("$ARGV[0]/*/*_3A.tif"))
{
  #system("./proc_planet_ry.py $tif");
  system("proc_planet_ry.py $tif");
}
