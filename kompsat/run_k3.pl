
foreach my $dir(glob("$ARGV[0]/K3*")){
   foreach my $tif(glob("$dir/K3*.TIF")){
      print "$tif\n";
      system("python kompsat3_toa.py $tif");
   }
}